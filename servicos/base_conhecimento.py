import hashlib
from dataclasses import replace
from pathlib import Path
from threading import RLock
import numpy as np
from dominio.erros import ErroIndexacao
from servicos.politica import validar_documento
from dominio.trecho_documento import TrechoDocumento
from servicos.processador_documento import dividir_em_trechos
from seguranca.extracao import extrair_protegido


def hash_arquivo(caminho):
    """Retorne SHA-256 do conteúdo ou lance ErroIndexacao sem expor caminho completo."""
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError as erro:
        raise ErroIndexacao('Não foi possível abrir o documento.') from erro


class BaseConhecimento:
    def __init__(self, repositorio, embedder, modelo_embedding=None):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self.repositorio = repositorio
        self._embedder = embedder
        self._modelo_embedding = modelo_embedding or embedder.nome_modelo
        self._indice = ([], np.empty((0, 0), dtype=np.float32))
        self._trava = RLock()

    @property
    def total_trechos(self):
        """Retorne o número de trechos no snapshot atualmente carregado."""
        return len(self._indice[0])

    def carregar(self):
        """Carregue ou retorne o snapshot de trechos e vetores compatíveis com o modelo."""
        self._indice = self.repositorio.carregar(self._modelo_embedding)

    def indexar_arquivo(self, caminho: Path, forcar=False, tamanho_trecho=450, metadados=None):
        """Valide, gere embeddings e publique o documento atomicamente; retorne a quantidade de trechos.
        
        Args:
            caminho: Caminho local do documento a processar.
            forcar: Se verdadeiro, reindexa mesmo quando o conteúdo não mudou.
            tamanho_trecho: Limite inicial de caracteres por trecho.
            metadados: Metadados públicos opcionais de curso, período e vigência.
        
        Returns:
            Quantidade de trechos publicados; zero indica versão já indexada.
        """
        hash_atual = hash_arquivo(caminho)
        if not forcar and metadados is None and self.repositorio.indexado(
                hash_atual, self._modelo_embedding, caminho.name):
            return 0
        trechos = self._preparar_trechos(caminho, tamanho_trecho)
        embeddings = self._embedder.codificar([t.texto for t in trechos])
        self._salvar(hash_atual, trechos, embeddings, metadados)
        return len(trechos)

    def _preparar_trechos(self, caminho, tamanho):
        """Extraia e valide páginas públicas; retorne trechos limitados em tamanho e quantidade."""
        trechos = [TrechoDocumento(caminho.name, pagina, texto)
                   for pagina, conteudo in self._paginas_publicas(caminho)
                   for texto in self._dividir(conteudo, tamanho)]
        if not trechos:
            raise ErroIndexacao('O documento não tem texto extraível.')
        if len(trechos) > 20000:
            raise ErroIndexacao('Documento excede 20.000 trechos. Divida o arquivo.')
        return trechos

    def _dividir(self, conteudo, tamanho):
        """Divida conteúdo em trechos, aplicando limites adicionais do adaptador quando disponíveis."""
        partes = dividir_em_trechos(conteudo, tamanho, tamanho // 6)
        dividir = getattr(self._embedder, 'dividir_tokens', None)
        return [fatia for parte in partes for fatia in dividir(parte)] if dividir else partes

    def buscar(self, pergunta, k=5):
        """Recarregue o acervo vigente e retorne até k trechos ordenados por similaridade.
        
        Args:
            pergunta: Pergunta pública validada, sem identificadores pessoais.
            k: Quantidade máxima de trechos retornados.
        
        Returns:
            Lista de trechos com pontuação de similaridade.
        """
        with self._trava:
            self.carregar()  # snapshot consistente, inclusive após mudanças em outro processo
            trechos, matriz = self._indice
        if not trechos:
            return []
        vetor = self._vetor_consulta(pergunta)
        return selecionar(trechos, matriz @ vetor, k)

    def _paginas_publicas(self, caminho):
        """Valide todas as páginas antes de gerar qualquer embedding remoto."""
        paginas = extrair_protegido(caminho)
        validar_documento(caminho.name)
        for _, texto in paginas:
            validar_documento(texto)
        return paginas

    def _vetor_consulta(self, pergunta):
        """Retorne embedding de consulta, preservando adaptadores lexicais de teste."""
        consulta = getattr(self._embedder, 'consulta', None)
        return consulta(pergunta) if consulta else self._embedder.codificar([pergunta])[0]

    def _salvar(self, hash_atual, trechos, embeddings, metadados):
        """Publique vetores e atualize o snapshot sob a mesma trava local."""
        with self._trava:
            self.repositorio.substituir_arquivo(hash_atual, self._modelo_embedding, trechos, embeddings, metadados)
            self.carregar()


def selecionar(trechos, similaridades, k):
    """Retorne até k trechos ordenados por similaridade decrescente."""
    k = min(max(1, k), len(trechos))
    candidatos = np.argpartition(-similaridades, k - 1)[:k]
    melhores = candidatos[np.argsort(-similaridades[candidatos])]
    return [replace(trechos[i], similaridade=float(similaridades[i])) for i in melhores]
