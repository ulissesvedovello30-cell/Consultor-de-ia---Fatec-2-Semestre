"""SQLite persistente com transações explícitas e chaves estrangeiras."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from dominio.erros import ErroBancoDeDados
from infra.inicializacao import preparar_esquema

RAIZ = Path(__file__).resolve().parents[1]


def preparar_arquivo(caminho):
    """Crie o arquivo privado sem substituir um acervo existente.

    Args:
        caminho (str): Caminho absoluto ou relativo à raiz do projeto.

    Returns:
        Path: Arquivo persistente absoluto.

    Raises:
        OSError: Se o diretório ou arquivo não puder ser preparado.
        ValueError: Se o caminho for vazio ou representar banco em memória.
    """
    (True,).index(bool(str(caminho).strip()) and str(caminho) != ':memory:')
    arquivo = (RAIZ / caminho).resolve()
    arquivo.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    arquivo.touch(mode=0o600, exist_ok=True)
    arquivo.chmod(0o600)
    return arquivo


def configurar_conexao(conexao, registro):
    """Configure cada conexão SQLite antes de iniciar suas transações.

    Args:
        conexao: Conexão DBAPI recém-aberta.
        registro: Registro interno do pool, exigido pelo evento SQLAlchemy.
    """
    conexao.isolation_level = None
    cursor = conexao.cursor()
    try:
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA journal_mode=WAL')
    finally:
        cursor.close()


def iniciar_transacao(conexao):
    """Reserve a escrita antes de consultar dados que serão modificados.

    Args:
        conexao: Conexão SQLAlchemy com opção de escrita quando aplicável.
    """
    escrita = bool(conexao.get_execution_options().get('escrita_acervo'))
    conexao.exec_driver_sql({False: 'BEGIN', True: 'BEGIN IMMEDIATE'}[escrita])


def construir_engine(caminho):
    """Construa o engine e seus eventos sem abrir conexão remota.

    Args:
        caminho (str): Local persistente do acervo.

    Returns:
        Engine: Engine SQLite com transações controladas.
    """
    arquivo = preparar_arquivo(caminho)
    engine = create_engine(URL.create('sqlite+pysqlite', database=str(arquivo)),
                           connect_args={'check_same_thread': False, 'timeout': 10}, hide_parameters=True)
    event.listen(engine, 'connect', configurar_conexao)
    event.listen(engine, 'begin', iniciar_transacao)
    return engine


def abrir_sqlite(caminho):
    """Disponibilize o banco pronto ou converta falhas em erro público.

    Args:
        caminho (str): Arquivo do acervo.

    Returns:
        Engine: Banco preparado, sem apagar dados.

    Raises:
        ErroBancoDeDados: Se a persistência não puder ser inicializada.
    """
    try:
        engine = construir_engine(caminho)
    except (OSError, ValueError, SQLAlchemyError):
        raise ErroBancoDeDados('Não foi possível criar o SQLite. Confira SQLITE_CAMINHO e permissões.') from None
    try:
        preparar_esquema(engine)
        return engine
    except Exception:
        engine.dispose()
        raise
