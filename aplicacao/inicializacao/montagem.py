"""Composição do RAG Gemini com a persistência selecionada."""
from contextlib import contextmanager
import aplicacao.configuracao.parametros as config
from aplicacao.core.chatbot import Chatbot
from aplicacao.infra.persistencia.banco_de_dados import criar_engine
from aplicacao.servicos.acervo.inicializar_acervo import preparar_primeira_carga
from aplicacao.infra.gemini.gemini_http import ClienteGemini
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_conhecimento import BaseConhecimento
from aplicacao.servicos.acervo.base_textual import BaseTextual
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.servicos.gemini.gemini import EmbeddingsGemini, GeradorGemini
from aplicacao.servicos.acervo.documentos_reais import retirar_exemplos


def criar_base(engine, cliente):
    """Monte e carregue o acervo com embeddings Gemini, sem transmitir documentos aqui."""
    repo = RepositorioTrechos(engine)
    base = escolher_busca(repo, cliente)
    retirar_exemplos(base.repositorio)
    base.carregar()
    return base


def montar(engine, cliente):
    """Retorne chatbot e base oficiais com limites e orçamento temporal."""
    base = criar_base(engine, cliente)
    gerador = GeradorGemini(cliente, config.MODELO_GERADOR)
    consultor = ConsultorRAG(base, gerador, limiar_similaridade=getattr(base, 'limiar_relevancia', config.RAG_LIMIAR_SIMILARIDADE),
                            prazo=config.RAG_TEMPO_GERACAO)
    return Chatbot(consultor), base


@contextmanager
def abrir_chatbot():
    """Disponibilize recursos oficiais e libere banco e cliente ao encerrar."""
    config.validar_gemini()
    cliente = ClienteGemini(config.GEMINI_API_KEY)
    try:
        with banco_aberto() as engine:
            chatbot, base = montar(engine, cliente)
            preparar_primeira_carga(engine, base)
            yield chatbot, base
    finally:
        cliente.fechar()


@contextmanager
def banco_aberto():
    """Disponibilize engine persistente com fechamento garantido, inclusive em erro."""
    engine = criar_engine(config.PERFIL, config.SQLITE_CAMINHO)
    try:
        yield engine
    finally:
        engine.dispose()


def escolher_busca(repo, cliente):
    """Escolha explicitamente a busca textual ou o embedding remoto.

    Args:
        repo: Repositório de documentos.
        cliente: Cliente Gemini para o modo vetorial opcional.

    Returns:
        BaseConhecimento: Busca textual por padrão; Gemini somente se solicitado.
    """
    if config.BUSCA_ACERVO == 'textual':
        return BaseTextual(repo)
    return BaseConhecimento(repo, EmbeddingsGemini(cliente, config.MODELO_EMBEDDING))
