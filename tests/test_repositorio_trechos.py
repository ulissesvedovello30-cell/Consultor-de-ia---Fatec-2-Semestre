"""Repositório testado em SQLite em memória: o mesmo código SQLAlchemy roda no MySQL."""
import numpy as np
import pytest
from sqlalchemy import Column, Integer, LargeBinary, MetaData, String, Table, Text, create_engine
from sqlalchemy.pool import StaticPool

from dominio.erros import ErroBancoDeDados
from dominio.trecho_documento import TrechoDocumento
from infra.repositorio_trechos import RepositorioTrechos

MODELO = "modelo-a"


def _tabela() -> Table:
    # Espelho de infra/schema_rag.sql, só para o teste. Em produção a tabela vem do banco.
    return Table(
        "trecho_documento",
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("hash_arquivo", String(64), nullable=False),
        Column("arquivo", String(255), nullable=False),
        Column("pagina", Integer, nullable=True),
        Column("texto", Text, nullable=False),
        Column("modelo_embedding", String(150), nullable=False),
        Column("embedding", LargeBinary, nullable=False),
    )


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", poolclass=StaticPool)  # uma única conexão em memória
    _tabela().metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def repositorio(engine):
    return RepositorioTrechos(engine)  # sem passar a tabela: ela é lida do banco, como no MySQL


def _vetores(*linhas):
    return np.array(linhas, dtype=np.float32)


def test_grava_e_le_trechos_com_vetores_exatos_e_pagina_nula(repositorio):
    trechos = [TrechoDocumento("a.pdf", 3, "um"), TrechoDocumento("b.txt", None, "dois")]
    vetores = _vetores([0.1, 0.2, 0.3], [0.7071, -0.5, 0.25])

    repositorio.substituir_arquivo("h1", MODELO, trechos, vetores)
    lidos, matriz = repositorio.carregar(MODELO)

    assert [(t.arquivo, t.pagina, t.texto) for t in lidos] == [("a.pdf", 3, "um"), ("b.txt", None, "dois")]
    assert matriz.dtype == np.float32 and np.array_equal(matriz, vetores)


def test_indexado_considera_o_arquivo_e_o_modelo(repositorio):
    repositorio.substituir_arquivo("h1", MODELO, [TrechoDocumento("a.pdf", 1, "x")], _vetores([1, 0]))

    assert repositorio.indexado("h1", MODELO)
    assert not repositorio.indexado("h1", "outro-modelo")
    assert not repositorio.indexado("h2", MODELO)


def test_substituir_troca_so_o_arquivo_indicado(repositorio):
    repositorio.substituir_arquivo("h1", MODELO, [TrechoDocumento("a.pdf", 1, "velho")], _vetores([1, 0]))
    repositorio.substituir_arquivo("h2", MODELO, [TrechoDocumento("b.pdf", 1, "outro")], _vetores([0, 1]))

    repositorio.substituir_arquivo("h1", MODELO, [TrechoDocumento("a.pdf", 1, "novo")], _vetores([1, 0]))
    lidos, _ = repositorio.carregar(MODELO)

    assert sorted(t.texto for t in lidos) == ["novo", "outro"]


def test_falha_no_meio_desfaz_tudo_e_preserva_o_que_havia(repositorio):
    repositorio.substituir_arquivo("h1", MODELO, [TrechoDocumento("a.pdf", 1, "bom")], _vetores([1, 0]))
    ruins = [TrechoDocumento("a.pdf", 1, "novo"), TrechoDocumento("a.pdf", 2, None)]  # texto NULL viola NOT NULL

    with pytest.raises(ErroBancoDeDados):
        repositorio.substituir_arquivo("h1", MODELO, ruins, _vetores([1, 0], [0, 1]))

    lidos, _ = repositorio.carregar(MODELO)
    assert [t.texto for t in lidos] == ["bom"]  # o DELETE também foi desfeito


def test_carregar_filtra_por_modelo_e_banco_vazio_devolve_matriz_vazia(repositorio):
    repositorio.substituir_arquivo("h1", "modelo-a", [TrechoDocumento("a.pdf", 1, "x")], _vetores([1, 0]))
    repositorio.substituir_arquivo("h2", "modelo-b", [TrechoDocumento("b.pdf", 1, "y")], _vetores([1, 0, 0]))

    assert [t.texto for t in repositorio.carregar("modelo-a")[0]] == ["x"]  # dimensões diferentes não se misturam
    trechos, matriz = repositorio.carregar("modelo-c")
    assert trechos == [] and matriz.size == 0


def test_mais_trechos_que_o_tamanho_do_lote(repositorio):
    total = 450  # passa de 2 lotes de 200
    trechos = [TrechoDocumento("a.pdf", 1, f"t{i}") for i in range(total)]

    repositorio.substituir_arquivo("h1", MODELO, trechos, np.eye(total, 4, dtype=np.float32))
    lidos, matriz = repositorio.carregar(MODELO)

    assert [t.texto for t in lidos] == [f"t{i}" for i in range(total)] and matriz.shape == (total, 4)


def test_um_vetor_para_cada_trecho(repositorio):
    with pytest.raises(ValueError):
        repositorio.substituir_arquivo("h1", MODELO, [TrechoDocumento("a.pdf", 1, "x")], _vetores([1, 0], [0, 1]))


def test_tabela_inexistente_da_erro_que_manda_rodar_o_sql():
    engine = create_engine("sqlite://", poolclass=StaticPool)  # banco vazio: ninguém criou a tabela

    with pytest.raises(ErroBancoDeDados, match="schema_rag.sql"):
        RepositorioTrechos(engine)
