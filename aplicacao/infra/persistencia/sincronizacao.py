"""Registro das fontes locais para retirar PDFs removidos sem apagar uploads."""
from sqlalchemy import select, insert, delete
from sqlalchemy.exc import SQLAlchemyError
from aplicacao.infra.persistencia.esquema import fontes_locais
from aplicacao.infra.repositorios.repositorio_trechos import identidade
from aplicacao.dominio.erros import ErroBancoDeDados


def nomes_anteriores(engine):
    """Leia os nomes da última sincronização confirmada.

    Args:
        engine: Engine do acervo.

    Returns:
        set[str]: Nomes administrados pela pasta institucional.
    """
    try:
        with engine.connect() as conexao:
            return set(conexao.scalars(select(fontes_locais.c.nome)))
    except SQLAlchemyError:
        raise ErroBancoDeDados('Não foi possível consultar as fontes locais.') from None


def confirmar(engine, nomes):
    """Registre a lista somente após concluir a atualização das fontes.

    Args:
        engine: Engine persistente do acervo.
        nomes (set[str]): Nomes dos PDFs que continuam presentes.
    """
    try:
        with engine.connect().execution_options(escrita_acervo=True) as c, c.begin():
            c.execute(delete(fontes_locais))
            for nome in sorted(nomes):
                c.execute(insert(fontes_locais).values(nome=nome))
    except SQLAlchemyError:
        raise ErroBancoDeDados('Não foi possível confirmar a sincronização.') from None


def retirar_ausentes(engine, base, nomes):
    """Retire do índice somente documentos locais que saíram da pasta.

    Args:
        engine: Banco que mantém a lista anterior.
        base: Base de conhecimento ativa.
        nomes (set[str]): Nomes encontrados nesta inicialização.
    """
    for nome in nomes_anteriores(engine) - nomes:
        base.repositorio.excluir(identidade(nome))
    confirmar(engine, nomes)
    base.carregar()
