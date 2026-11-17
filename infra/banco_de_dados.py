"""Seleção de persistência; PostgreSQL fica reservado para a próxima etapa."""
from infra.sqlite import abrir_sqlite


def criar_engine(perfil='mvp', caminho='runtime/acervo.sqlite3'):
    """Selecione a persistência sem trocar silenciosamente de banco.

    Args:
        perfil (str): mvp disponível ou postgres reservado.
        caminho (str): Arquivo SQLite do acervo.

    Returns:
        Engine: Conexão configurada e esquema preparado.

    Raises:
        ValueError: Se o perfil não existir.
        NotImplementedError: Se PostgreSQL for solicitado nesta versão.
    """
    try:
        fabrica = {'mvp': abrir_sqlite, 'postgres': postgres_pendente}[perfil]
    except KeyError:
        raise ValueError('CHATBOT_PERFIL deve ser mvp ou postgres.') from None
    return fabrica(caminho)


def postgres_pendente(caminho):
    """Interrompa o perfil futuro antes de abrir banco ou chamar Gemini.

    Args:
        caminho (str): Parâmetro da fábrica, sem uso neste perfil.

    Raises:
        NotImplementedError: PostgreSQL e pgvector ainda não foram implementados.
    """
    raise NotImplementedError('Gemini + PostgreSQL está planejado. Use CHATBOT_PERFIL=mvp nesta versão.')
