"""Montagem isolada para testes; não é um modo executável do chatbot."""
from core.chatbot import Chatbot
from infra.esquema import metadata
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from tests.dubles_rag import EmbeddingsLexicais, GeradorExtrativo
from servicos.acervo_institucional import carregar_iniciais


def montar_acervo_teste(engine):
    """Monte SQLite local com fontes reais e recuperação lexical de teste."""
    metadata.create_all(engine)
    base = BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    carregar_iniciais(base)
    base.carregar()
    return Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.2)), base
