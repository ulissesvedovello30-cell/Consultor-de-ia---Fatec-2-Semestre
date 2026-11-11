"""Composição do RAG Gemini com a persistência selecionada."""
from contextlib import contextmanager
import config
from core.chatbot import Chatbot
from infra.banco_de_dados import criar_engine
from servicos.inicializar_acervo import preparar_primeira_carga
from infra.gemini_http import ClienteGemini
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.base_textual import BaseTextual
from servicos.consultor_rag import ConsultorRAG
from servicos.gemini import EmbeddingsGemini, GeradorGemini
from servicos.documentos_reais import retirar_exemplos


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
