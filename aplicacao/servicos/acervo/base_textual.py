"""RAG textual persistente: recupera evidências sem cota de embeddings."""
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from aplicacao.servicos.recuperacao.planejamento.identidade import identificar_resultados
from threading import RLock
from aplicacao.servicos.recuperacao.linguagem.indice import IndiceLinguistico
from aplicacao.servicos.recuperacao.linguagem.fusao import combinar
from aplicacao.infra.persistencia.consultas_acervo import consulta_vigente, converter_trecho, juntar_ativos
from aplicacao.infra.persistencia.esquema import documentos, versoes
from aplicacao.infra.repositorios.indice_textual import criar_indice, buscar
from aplicacao.servicos.acervo.base_conhecimento import BaseConhecimento, hash_arquivo
from aplicacao.servicos.acervo.documentos_reais import conferir_documento
from aplicacao.servicos.recuperacao.consulta_textual import termos_consulta, expressao, cobertura
from aplicacao.servicos.recuperacao.faq import localizar, eh_faq_customizada, recortar_faq_customizada
from aplicacao.servicos.recuperacao.filtros_acervo import mencionados, expandir_cursos, normalizar, forma_curso
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta

MODELO_TEXTUAL = 'sqlite-fts5-unicode61-bm25:pdf-calendario-ppc-faq-v5'


class BaseTextual(BaseConhecimento):
    """Reutilize validação e extração, mantendo separada a recuperação textual."""
    chave_carga = 'acervo_inicial_fts5_v1'
    limiar_relevancia = 0.6

    def __init__(self, repositorio):
        """Receba o repositório persistente; nenhum cliente de embeddings é criado."""
        self.repositorio = repositorio
        self._modelo_embedding, self._embedder = MODELO_TEXTUAL, None
        self._trava, self._textos, self._assinatura_banco = RLock(), [], None
        self._linguistico = IndiceLinguistico()
        criar_indice(repositorio._engine)

    @property
    def total_trechos(self):
        """int: Quantidade de trechos textuais vigentes."""
        return len(self._textos)

    def _ler_assinatura_banco(self):
        """Consulte somente versões ativas e data atual para evitar recarga desnecessária."""
        hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        consulta = select(documentos.c.id, documentos.c.versao_ativa, versoes.c.inicio, versoes.c.fim).select_from(
            juntar_ativos()).where(versoes.c.modelo_embedding == self._modelo_embedding).order_by(documentos.c.id)
        linhas = self.repositorio._ler(consulta)
        return hoje, tuple((l['id'], l['versao_ativa'], l['inicio'], l['fim']) for l in linhas)

    def carregar(self):
        """Carregue fontes textuais vigentes somente quando versões ou vigência mudarem."""
        with self._trava:
            assinatura = self._ler_assinatura_banco()
            if assinatura == self._assinatura_banco:
                return
            self._textos = [converter_trecho(l) for l in
                            self.repositorio._ler(consulta_vigente(self._modelo_embedding, incluir_embedding=False))]
            self._assinatura_banco = assinatura

    def indexar_arquivo(self, caminho, forcar=False, tamanho_trecho=1000, metadados=None):
        """Valide e publique o texto completo na transação do documento."""
        digest = hash_arquivo(caminho)
        conferir_documento(digest)
        if not forcar and metadados is None and self.repositorio.indexado(digest, self._modelo_embedding, caminho.name):
            return 0
        partes = self._preparar_trechos(caminho, tamanho_trecho)
        with self._trava:
            self.repositorio.substituir_textos(digest, self._modelo_embedding, partes, metadados)
            self._assinatura_banco = None
            self.carregar()
        return len(partes)

    def buscar(self, pergunta, k=5):
        """Recupere fontes por FAQ exata ou BM25; não use a API de embeddings."""
        with self._trava:
            self.carregar()
            return identificar_resultados(self._recuperar(preparar_consulta(pergunta), k), self._textos)

    def _recuperar(self, pergunta, k):
        """Consulte intenções documentais antes de combinar as buscas lexicais.

        Args:
            pergunta (str): Pergunta recebida.
            k (int): Máximo de resultados.

        Returns:
            list: Evidências vigentes, obtidas no mesmo snapshot protegido.
        """
        from aplicacao.servicos.recuperacao.intencao import buscar_contexto
        contexto = buscar_contexto(pergunta, self._textos, k)
        if contexto is not None:
            return contexto
        return localizar(pergunta, self._textos)[:k] or self._buscar_termos(pergunta, k)

    def _buscar_termos(self, pergunta, k):
        """Filtre o curso antes do BM25 e descarte correspondências muito parciais."""
        cursos = mencionados(pergunta, {t.curso for t in self._textos if t.curso})
        ignoradas_curso = {normalizar(c) for c in cursos} | {forma_curso(c) for c in cursos}
        palavras = termos_consulta(expandir_cursos(normalizar(pergunta)), ignoradas_curso)
        if not palavras:
            return []
        candidatos = self._candidatos(palavras, k, cursos)
        pontuados = [replace(t, similaridade=cobertura(palavras, t.texto)) for t in candidatos]
        self._linguistico.atualizar(self._textos)
        linguistica = self._linguistico.buscar(palavras, cursos)
        resultado = []
        for t in combinar((pontuados, linguistica), palavras, k):
            if t.arquivo == 'FAQ_secretaria.txt':
                if eh_faq_customizada(t):
                    resultado.append(recortar_faq_customizada(t))
            else:
                resultado.append(t)
        return resultado

    def _candidatos(self, palavras, k, cursos):
        """Priorize cobertura integral antes de limitar o conjunto de evidências.

        Args:
            palavras (set[str]): Assuntos relevantes da pergunta.
            k (int): Quantidade de resultados solicitada.
            cursos (set[str]): Cursos explicitamente mencionados.

        Returns:
            list: Candidatos vigentes, ordenados por BM25 dentro de cada busca.
        """
        limite = min(200, max(50, k * 20))
        completos = buscar(self.repositorio, self._modelo_embedding,
                           expressao(palavras, 'AND'), limite, cursos)
        return completos or buscar(self.repositorio, self._modelo_embedding,
                                    expressao(palavras), limite, cursos)
