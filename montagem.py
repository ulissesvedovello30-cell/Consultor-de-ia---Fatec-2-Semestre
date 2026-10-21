"""Monta o chatbot de verdade: MySQL existente + modelos locais do Hugging Face.

É o ponto de integração: o back-end do site (ou qualquer outro canal) faz

    with abrir_chatbot() as (chatbot, base):
        resposta = await chatbot.processar_mensagem(id_da_conversa, texto)

uma vez ao subir e reaproveita o `chatbot` em todas as requisições.
"""
import logging
from contextlib import contextmanager

import config
from core.chatbot import Chatbot
from infra.banco_de_dados import ConfigBanco, criar_engine
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.gerador_embeddings import GeradorEmbeddings
from servicos.gerador_local import GeradorLocal

logger = logging.getLogger(__name__)


def configurar_banco() -> ConfigBanco:
    return ConfigBanco(
        host=config.MYSQL_HOST,
        usuario=config.MYSQL_USUARIO,
        senha=config.MYSQL_SENHA,
        database=config.MYSQL_DATABASE,
    )


@contextmanager
def abrir_chatbot():
    """Entrega (chatbot, base de conhecimento) e fecha as conexões ao sair."""
    engine = criar_engine(configurar_banco())
    try:
        embedder = GeradorEmbeddings(config.MODELO_EMBEDDING)
        gerador = GeradorLocal(config.MODELO_GERADOR, tempo_limite=config.RAG_TEMPO_GERACAO)

        base = BaseConhecimento(RepositorioTrechos(engine), embedder)
        base.carregar()
        if base.total_trechos == 0:
            logger.warning("Nenhum documento indexado: rode `python indexar_pdfs.py arquivo.pdf` antes.")

        # Falhar cedo: baixar/carregar os modelos agora, não na pergunta do primeiro aluno.
        embedder.carregar()
        gerador.carregar()

        consultor = ConsultorRAG(base, gerador, limiar_similaridade=config.RAG_LIMIAR_SIMILARIDADE)
        yield Chatbot(consultor), base
    finally:
        engine.dispose()
