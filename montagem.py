"""Composição do atendimento oficial: MySQL existente e API Gemini."""
from contextlib import contextmanager
import config
from core.chatbot import Chatbot
from infra.banco_de_dados import ConfigBanco, criar_engine
from infra.gemini_http import ClienteGemini
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.gemini import EmbeddingsGemini, GeradorGemini


def configurar_banco():
    """Retorne credenciais e parâmetros MySQL definidos no ambiente do servidor."""
    return ConfigBanco(host=config.MYSQL_HOST, usuario=config.MYSQL_USUARIO,
        senha=config.MYSQL_SENHA, database=config.MYSQL_DATABASE, porta=config.MYSQL_PORTA)


def criar_base(engine, cliente):
    """Monte e carregue o acervo com embeddings Gemini, sem transmitir documentos aqui."""
    embedder = EmbeddingsGemini(cliente, config.MODELO_EMBEDDING)
    base = BaseConhecimento(RepositorioTrechos(engine), embedder)
    base.carregar()
    return base


def montar(engine, cliente):
    """Retorne chatbot e base oficiais com limites e orçamento temporal."""
    base = criar_base(engine, cliente)
    gerador = GeradorGemini(cliente, config.MODELO_GERADOR)
    consultor = ConsultorRAG(base, gerador, limiar_similaridade=config.RAG_LIMIAR_SIMILARIDADE,
                            prazo=config.RAG_TEMPO_GERACAO)
    return Chatbot(consultor), base


@contextmanager
def abrir_chatbot():
    """Disponibilize recursos oficiais e libere banco e cliente ao encerrar."""
    cliente = ClienteGemini(config.GEMINI_API_KEY)
    try:
        with banco_aberto() as engine:
            yield montar(engine, cliente)
    finally:
        cliente.fechar()


@contextmanager
def banco_aberto():
    """Disponibilize engine MySQL com fechamento garantido, inclusive em erro."""
    engine = criar_engine(configurar_banco())
    try:
        yield engine
    finally:
        engine.dispose()
