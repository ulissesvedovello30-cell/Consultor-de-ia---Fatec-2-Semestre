"""Versões imutáveis; troca atômica do ponteiro ativo por documento."""
import hashlib
import unicodedata
import uuid
import numpy as np
from sqlalchemy import select, insert, update, delete
from sqlalchemy.exc import SQLAlchemyError
from dominio.erros import ErroBancoDeDados
from dominio.metadados import Metadados
from infra.esquema import documentos as d, versoes as v, trechos as t
from infra.consultas_acervo import consulta_vigente, converter_indice, juntar_ativos


def identidade(nome):
    """Retorne ID estável do nome normalizado, independente do conteúdo do arquivo."""
    normalizado = unicodedata.normalize('NFC', nome).casefold()
    return hashlib.sha256(normalizado.encode()).hexdigest()


def linha_trecho(trecho, vetor, versao):
    """Serialize um trecho e seu vetor float32 little-endian para persistência."""
    return dict(versao_id=versao, pagina=trecho.pagina, texto=trecho.texto,
                embedding=np.asarray(vetor, dtype='<f4').tobytes())


class RepositorioTrechos:
    def __init__(self, engine, tabela=None):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self._engine = engine
        self._ler(select(d.c.id).limit(1))

    def _ler(self, consulta):
        """Execute consulta SQL e converta falhas em ErroBancoDeDados sanitizado."""
        try:
            with self._engine.connect() as conexao:
                return conexao.execute(consulta).mappings().all()
        except SQLAlchemyError as erro:
            raise ErroBancoDeDados('Falha no acervo. Confira infra/schema_rag.sql e a conexão.') from erro

    def indexado(self, hash_arquivo, modelo_embedding, nome=None):
        """Verifique se a versão ativa corresponde a conteúdo, modelo e nome informados."""
        consulta = select(v.c.id).select_from(juntar_ativos()).where(
            v.c.hash_arquivo == hash_arquivo, v.c.modelo_embedding == modelo_embedding)
        if nome is not None:
            consulta = consulta.where(d.c.id == identidade(nome))
        return bool(self._ler(consulta.limit(1)))

    def substituir_arquivo(self, hash_arquivo, modelo_embedding, trechos, embeddings, metadados=None):
        """Publique uma nova versão em transação e elimine versões antigas após a troca.
        
        Args:
            hash_arquivo: SHA-256 do conteúdo documental.
            modelo_embedding: Identidade do modelo e configuração dos vetores.
            trechos: Sequência de trechos públicos a persistir ou consultar.
            embeddings: Matriz de vetores alinhada à sequência de trechos.
            metadados: Metadados públicos opcionais de curso, período e vigência.
        """
        validar_lote(trechos, embeddings)
        versao = uuid.uuid4().hex
        dados = (hash_arquivo, modelo_embedding, metadados)
        linhas = [linha_trecho(a, b, versao) for a, b in zip(trechos, embeddings)]
        try:
            with self._engine.begin() as conexao:
                self._gravar(conexao, trechos[0].arquivo, versao, dados, linhas)
        except SQLAlchemyError as erro:
            raise ErroBancoDeDados('Falha ao atualizar o acervo; transação desfeita.') from erro

    def _gravar(self, conexao, nome, versao, dados, linhas):
        """Grave documento, versão e trechos dentro da transação recebida."""
        documento_id = identidade(nome)
        self._garantir_documento(conexao, documento_id, nome)
        hash_arquivo, modelo, metadados = dados
        metadados = metadados or self._metadados_atuais(conexao, documento_id)
        conexao.execute(insert(v).values(id=versao, documento_id=documento_id,
            hash_arquivo=hash_arquivo, modelo_embedding=modelo, **metadados.valores()))
        for inicio in range(0, len(linhas), 200):
            conexao.execute(insert(t), linhas[inicio:inicio + 200])
        conexao.execute(update(d).where(d.c.id == documento_id).values(versao_ativa=versao, nome=nome))
        apagar_versoes(conexao, documento_id, versao)

    def _garantir_documento(self, conexao, documento_id, nome):
        """Bloqueie o documento existente ou insira sua identidade na transação."""
        consulta = select(d.c.id).where(d.c.id == documento_id).with_for_update()
        if conexao.execute(consulta).first() is None:
            conexao.execute(insert(d).values(id=documento_id, nome=nome))

    def carregar(self, modelo_embedding):
        """Carregue ou retorne o snapshot de trechos e vetores compatíveis com o modelo."""
        try:
            return converter_indice(self._ler(consulta_vigente(modelo_embedding)))
        except (ValueError, TypeError) as erro:
            raise ErroBancoDeDados('Índice incompatível; reindexe os documentos.') from erro

    def listar(self):
        """Retorne documentos publicados e metadados de suas versões ativas."""
        consulta = select(d.c.id, d.c.nome, v).select_from(juntar_ativos()).order_by(d.c.nome)
        return [dict(linha) for linha in self._ler(consulta)]

    def excluir(self, documento_id):
        """Remova o documento e suas versões, mantendo atomicidade da operação."""
        try:
            with self._engine.begin() as conexao:
                existente = conexao.execute(select(d.c.id).where(d.c.id == documento_id).with_for_update()).first()
                conexao.execute(update(d).where(d.c.id == documento_id).values(versao_ativa=None))
                apagar_versoes(conexao, documento_id)
                conexao.execute(delete(d).where(d.c.id == documento_id))
                return existente is not None
        except SQLAlchemyError as erro:
            raise ErroBancoDeDados('Falha ao retirar documento do acervo.') from erro

    def fonte(self, documento_id, versao_id):
        """Retorne o texto de uma versão ainda ativa ou informe ausência."""
        consulta = select(t.c.pagina, t.c.texto).select_from(juntar_ativos().join(
            t, t.c.versao_id == v.c.id)).where(d.c.id == documento_id, v.c.id == versao_id)
        return [dict(linha) for linha in self._ler(consulta.order_by(t.c.id))]

    def _metadados_atuais(self, conexao, documento_id):
        """Retorne metadados da versão ativa ou valores vazios para documento novo."""
        campos = ('curso', 'periodo', 'ano', 'inicio', 'fim', 'url_oficial')
        consulta = select(*(v.c[c] for c in campos)).select_from(juntar_ativos()).where(d.c.id == documento_id)
        linha = conexao.execute(consulta).mappings().first()
        return Metadados(**dict(linha)) if linha else Metadados()


def apagar_versoes(conexao, documento_id, manter=None):
    """Apague textos e vetores antigos na transação; mantenha só a versão indicada."""
    filtro = v.c.documento_id == documento_id
    if manter is not None:
        filtro = filtro & (v.c.id != manter)
    ids = [r[0] for r in conexao.execute(select(v.c.id).where(filtro))]
    for versao in ids:
        conexao.execute(delete(t).where(t.c.versao_id == versao))
    conexao.execute(delete(v).where(filtro))


def validar_lote(trechos, embeddings):
    """Exija um documento, um vetor finito por trecho e dimensão uniforme."""
    if not trechos or len(trechos) != len(embeddings):
        raise ValueError('Cada trecho precisa de exatamente um vetor.')
    if len({trecho.arquivo for trecho in trechos}) != 1:
        raise ValueError('Cada operação substitui apenas um documento.')
    if np.ndim(embeddings) != 2 or not np.isfinite(embeddings).all():
        raise ValueError('Matriz de embeddings inválida.')
