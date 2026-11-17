"""Montagem isolada para testes; não é um modo executável do chatbot."""
from aplicacao.core.chatbot import Chatbot
from aplicacao.infra.persistencia.esquema import metadata
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_textual import BaseTextual
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from tests.apoio.dubles_rag import EmbeddingsLexicais, GeradorExtrativo
from aplicacao.servicos.acervo.acervo_institucional import carregar_iniciais


def montar_acervo_teste(engine):
    """Monte SQLite local com fontes reais e recuperação lexical de teste."""
    metadata.create_all(engine)
    base = BaseTextual(RepositorioTrechos(engine))
    carregar_iniciais(base)
    base.carregar()
    return Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.6)), base
