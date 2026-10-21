import numpy as np
import pytest

from dominio.trecho_documento import TrechoDocumento
from servicos import base_conhecimento
from servicos.base_conhecimento import BaseConhecimento

MODELO = "modelo-falso"


class EmbedderFalso:
    """Devolve vetores fixos por texto, no lugar do modelo de verdade."""

    def __init__(self, vetores: dict[str, list[float]]):
        self._vetores = vetores

    def codificar(self, textos):
        return np.array([self._vetores[t] for t in textos], dtype=np.float32)


class RepositorioFalso:
    def __init__(self, trechos=(), matriz=None, ja_indexado=False):
        self.trechos = list(trechos)
        self.matriz = np.empty((0, 0), dtype=np.float32) if matriz is None else np.array(matriz, dtype=np.float32)
        self.ja_indexado = ja_indexado
        self.substituicoes = []

    def carregar(self, modelo):
        return self.trechos, self.matriz

    def indexado(self, hash_arquivo, modelo):
        return self.ja_indexado

    def substituir_arquivo(self, hash_arquivo, modelo, trechos, embeddings):
        self.substituicoes.append((hash_arquivo, modelo, trechos, embeddings))


def _base_com_tres_trechos():
    trechos = [TrechoDocumento("a.pdf", 1, "gato"), TrechoDocumento("a.pdf", 2, "cachorro"), TrechoDocumento("b.pdf", 7, "misto")]
    matriz = [[1, 0], [0, 1], [0.70710677, 0.70710677]]
    embedder = EmbedderFalso({"pergunta sobre gato": [1, 0]})
    base = BaseConhecimento(RepositorioFalso(trechos, matriz), embedder, MODELO)
    base.carregar()
    return base


def test_busca_devolve_do_mais_para_o_menos_parecido():
    resultado = _base_com_tres_trechos().buscar("pergunta sobre gato", k=3)

    assert [t.texto for t in resultado] == ["gato", "misto", "cachorro"]
    assert resultado[0].similaridade == pytest.approx(1.0)
    assert resultado[1].similaridade == pytest.approx(0.7071, abs=1e-3)
    assert (resultado[1].arquivo, resultado[1].pagina) == ("b.pdf", 7)


def test_busca_respeita_k_e_nao_estoura_quando_k_passa_do_total():
    base = _base_com_tres_trechos()

    assert [t.texto for t in base.buscar("pergunta sobre gato", k=1)] == ["gato"]
    assert len(base.buscar("pergunta sobre gato", k=50)) == 3


def test_base_vazia_nao_busca_nada():
    base = BaseConhecimento(RepositorioFalso(), EmbedderFalso({}), MODELO)
    base.carregar()

    assert base.buscar("qualquer coisa") == []


@pytest.fixture
def pdf_falso(tmp_path, monkeypatch):
    caminho = tmp_path / "regimento.pdf"
    caminho.write_bytes(b"conteudo qualquer")
    monkeypatch.setattr(base_conhecimento, "extrair_paginas", lambda c: [(1, "texto da pagina um"), (2, "texto da pagina dois")])
    return caminho


def test_indexar_grava_trechos_com_nome_do_arquivo_e_pagina(pdf_falso):
    repositorio = RepositorioFalso()
    embedder = EmbedderFalso({"texto da pagina um": [1, 0], "texto da pagina dois": [0, 1]})
    base = BaseConhecimento(repositorio, embedder, MODELO)

    total = base.indexar_arquivo(pdf_falso)

    assert total == 2
    (hash_arquivo, modelo, trechos, embeddings), = repositorio.substituicoes
    assert len(hash_arquivo) == 64 and modelo == MODELO
    assert [(t.arquivo, t.pagina) for t in trechos] == [("regimento.pdf", 1), ("regimento.pdf", 2)]  # sem o caminho da máquina
    assert embeddings.shape == (2, 2)


def test_indexar_pula_pdf_que_ja_esta_no_banco_a_menos_que_force(pdf_falso):
    repositorio = RepositorioFalso(ja_indexado=True)
    embedder = EmbedderFalso({"texto da pagina um": [1, 0], "texto da pagina dois": [0, 1]})
    base = BaseConhecimento(repositorio, embedder, MODELO)

    assert base.indexar_arquivo(pdf_falso) == 0
    assert repositorio.substituicoes == []

    assert base.indexar_arquivo(pdf_falso, forcar=True) == 2
    assert len(repositorio.substituicoes) == 1
