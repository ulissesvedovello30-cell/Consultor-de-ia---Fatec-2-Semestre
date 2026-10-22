"""Debug removível. Nunca é selecionado automaticamente no atendimento oficial."""
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine
from core.chatbot import Chatbot
from infra.esquema import metadata
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.demo_offline import EmbeddingsLexicais, GeradorExtrativo


def montar_demo(engine):
    """Monte o acervo SQLite com documentos fictícios e recuperação lexical."""
    metadata.create_all(engine)  # permitido apenas no SQLite exclusivo de debug
    base = BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    caminho = Path(__file__).parent / 'dados/turma_exemplo.txt'
    base.indexar_arquivo(caminho)
    base.carregar()
    return Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.2)), base


@contextmanager
def abrir_demo():
    """Disponibilize o ambiente de demonstração e feche o banco ao encerrar."""
    pasta = Path(__file__).parent / 'runtime'
    pasta.mkdir(exist_ok=True)
    engine = create_engine('sqlite:///' + str(pasta / 'debug.sqlite3'),
                           connect_args={'check_same_thread': False})
    try:
        yield montar_demo(engine)
    finally:
        engine.dispose()
