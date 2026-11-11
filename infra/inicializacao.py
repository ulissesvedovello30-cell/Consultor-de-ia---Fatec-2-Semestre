"""Preparação idempotente do esquema e controle da primeira carga."""
from sqlalchemy import select, insert, delete
from sqlalchemy.exc import SQLAlchemyError
from dominio.erros import ErroBancoDeDados
from infra.esquema import metadata, inicializacao, lotes_iniciais

CHAVE = 'acervo_inicial'


def preparar_esquema(engine):
    """Crie tabelas ausentes sem recriar ou apagar as existentes.

    Args:
        engine: Engine com suporte à opção escrita_acervo.

    Raises:
        ErroBancoDeDados: Se o arquivo estiver incompatível ou indisponível.
    """
    try:
        with engine.connect().execution_options(escrita_acervo=True) as conexao:
            with conexao.begin():
                metadata.create_all(conexao, checkfirst=True)
    except SQLAlchemyError:
        raise ErroBancoDeDados('Não foi possível preparar o esquema do acervo.') from None


def carga_concluida(engine, chave=CHAVE):
    """Consulte o registro persistente da primeira carga bem-sucedida.

    Args:
        engine: Engine do acervo.

    Returns:
        bool: True depois da publicação inicial completa.
    """
    try:
        with engine.connect() as conexao:
            return conexao.scalar(select(inicializacao.c.chave).where(inicializacao.c.chave == chave)) is not None
    except SQLAlchemyError:
        raise ErroBancoDeDados('Não foi possível consultar a inicialização do acervo.') from None


def registrar_carga(engine, chave=CHAVE):
    """Registre a conclusão sem acoplar esse estado aos documentos publicados.

    Args:
        engine: Engine do acervo.

    Raises:
        ErroBancoDeDados: Se o registro não puder ser confirmado.
    """
    try:
        with engine.connect().execution_options(escrita_acervo=True) as conexao:
            with conexao.begin():
                conexao.execute(delete(inicializacao).where(inicializacao.c.chave == chave))
                conexao.execute(insert(inicializacao).values(chave=chave))
                conexao.execute(delete(lotes_iniciais))
    except SQLAlchemyError:
        raise ErroBancoDeDados('Não foi possível registrar a carga inicial.') from None
