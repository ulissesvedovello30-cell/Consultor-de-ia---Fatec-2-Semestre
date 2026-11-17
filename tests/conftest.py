"""Acervo temporário dos PDFs reais, sem chamadas de rede na coleta."""
import pytest
from aplicacao.infra.persistencia.sqlite import abrir_sqlite
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_textual import BaseTextual
from aplicacao.servicos.acervo.inicializar_acervo import preparar_primeira_carga


@pytest.fixture(scope='session')
def base_pdf(tmp_path_factory):
    engine = abrir_sqlite(str(tmp_path_factory.mktemp('pdf-real') / 'acervo.db'))
    base = BaseTextual(RepositorioTrechos(engine))
    preparar_primeira_carga(engine, base)
    yield base
    engine.dispose()
