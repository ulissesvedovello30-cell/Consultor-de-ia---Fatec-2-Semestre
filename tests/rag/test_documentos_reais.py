"""Sincronização da pasta de PDFs com a base recriada pelo programa."""
from pathlib import Path
from shutil import copyfile
import pytest
from pypdf import PdfReader, PdfWriter
from aplicacao.configuracao.caminhos import DOCUMENTOS
from aplicacao.infra.persistencia.sqlite import abrir_sqlite
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_textual import BaseTextual
from aplicacao.servicos.acervo.inicializar_acervo import preparar_primeira_carga
from aplicacao.servicos.acervo import documentos_reais
from aplicacao.dominio.erros import ErroIndexacao


def gravar_pagina(caminho, numero):
    original = next(DOCUMENTOS.rglob('Calendario*.pdf'))
    escritor = PdfWriter()
    escritor.add_page(PdfReader(original).pages[numero])
    escritor.write(caminho)


@pytest.fixture
def acervo_local(tmp_path, monkeypatch):
    pasta = tmp_path / 'documentos'
    pasta.mkdir()
    gravar_pagina(pasta / 'calendario.pdf', 0)
    monkeypatch.setattr(documentos_reais, 'DOCUMENTOS', pasta)
    engine = abrir_sqlite(str(tmp_path / 'banco' / 'acervo.db'))
    base = BaseTextual(RepositorioTrechos(engine))
    yield engine, base, pasta
    engine.dispose()


def test_banco_novo_carga_e_reinicio_sem_reprocessar(acervo_local, monkeypatch):
    engine, base, _ = acervo_local
    assert sum(preparar_primeira_carga(engine, base).values()) > 0
    monkeypatch.setattr(base, '_preparar_trechos', lambda *a: pytest.fail('PDF idêntico foi reprocessado'))
    assert set(preparar_primeira_carga(engine, base).values()) == {0}
    assert base.total_trechos > 0


def test_pdf_substituido_atualiza_sem_apagar_o_banco(acervo_local):
    engine, base, pasta = acervo_local
    preparar_primeira_carga(engine, base)
    anterior = base.repositorio.listar()[0]['hash_arquivo']
    gravar_pagina(pasta / 'calendario.pdf', 1)
    assert sum(preparar_primeira_carga(engine, base).values()) > 0
    assert base.repositorio.listar()[0]['hash_arquivo'] != anterior
    assert len(base.repositorio.listar()) == 1


def test_pdf_removido_sai_do_indice_sem_apagar_upload(acervo_local):
    engine, base, pasta = acervo_local
    preparar_primeira_carga(engine, base)
    upload = pasta.parent / 'biblioteca.txt'
    upload.write_text('A biblioteca fica no bloco de atendimento ao estudante.')
    base.indexar_arquivo(upload)
    (pasta / 'calendario.pdf').rename(pasta / 'novo-calendario.pdf')
    preparar_primeira_carga(engine, base)
    assert {d['nome'] for d in base.repositorio.listar()} == {'novo-calendario.pdf', 'biblioteca.txt'}


def test_pasta_vazia_nao_confirma_carga_silenciosamente(acervo_local):
    engine, base, pasta = acervo_local
    (pasta / 'calendario.pdf').unlink()
    with pytest.raises(ErroIndexacao, match='Inclua PDFs'):
        preparar_primeira_carga(engine, base)


def test_pdf_corrompido_nao_substitui_versao_ativa(acervo_local):
    engine, base, pasta = acervo_local
    preparar_primeira_carga(engine, base)
    anterior = base.repositorio.listar()[0]['hash_arquivo']
    (pasta / 'calendario.pdf').write_bytes(b'%PDF-1.4 arquivo corrompido')
    with pytest.raises(ErroIndexacao):
        preparar_primeira_carga(engine, base)
    assert base.repositorio.listar()[0]['hash_arquivo'] == anterior
