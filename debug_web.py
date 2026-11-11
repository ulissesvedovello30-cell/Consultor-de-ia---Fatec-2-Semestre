"""Debug removível. Nunca é selecionado automaticamente no atendimento oficial."""
import logging
from contextlib import contextmanager, suppress
from pathlib import Path
from sqlalchemy import create_engine
from core.chatbot import Chatbot
from dominio.erros import ErroIndexacao
from infra.esquema import metadata
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.demo_offline import EmbeddingsLexicais, GeradorExtrativo
from servicos.pasta import documentos_da_pasta as listar

logger = logging.getLogger(__name__)
PASTA_DOCUMENTOS = Path(__file__).parent / 'documentos'


def documentos_da_pasta(pasta=PASTA_DOCUMENTOS):
    """Liste os documentos aceitos da pasta; arquivos novos entram na demonstração sem mexer no código."""
    return listar(pasta)


def indexar_sem_travar(base, caminho):
    """Indexe um documento; se for recusado, avise no log e siga, para um arquivo ruim não derrubar o demo."""
    try:
        base.indexar_arquivo(caminho)
    except ErroIndexacao as erro:
        logger.warning('Documento ignorado na demonstração (%s): %s', caminho.name, erro)


def montar_demo(engine, arquivos=None):
    """Monte o acervo SQLite com os documentos da pasta `documentos/` e recuperação lexical.

    Args:
        engine: Engine SQLite exclusivo de debug.
        arquivos: Lista de caminhos a indexar; por padrão, tudo o que estiver em `documentos/`.
    """
    metadata.create_all(engine)  # permitido apenas no SQLite exclusivo de debug
    base = BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    for caminho in documentos_da_pasta() if arquivos is None else arquivos:
        indexar_sem_travar(base, Path(caminho))
    base.carregar()
    return Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.2)), base


@contextmanager
def abrir_demo(arquivos=None):
    """Disponibilize a demonstração refeita a partir da pasta `documentos/` e feche o banco ao encerrar.

    O banco de debug é recriado a cada início para refletir exatamente a pasta: documento
    removido de lá some da demonstração, e documento novo entra sozinho.
    """
    pasta = Path(__file__).parent / 'runtime'
    pasta.mkdir(exist_ok=True)
    with suppress(OSError):  # em uso por outro processo: segue com o banco existente
        (pasta / 'debug.sqlite3').unlink(missing_ok=True)
    engine = create_engine('sqlite:///' + str(pasta / 'debug.sqlite3'),
                           connect_args={'check_same_thread': False})
    try:
        yield montar_demo(engine, arquivos)
    finally:
        engine.dispose()
