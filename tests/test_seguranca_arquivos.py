"""Testes de documentos ativos, extração isolada e limites de recursos."""
import subprocess
from pathlib import Path
from zipfile import ZipFile
import pytest
from dominio.erros import ErroIndexacao
from seguranca.arquivos import conferir_docx
from seguranca.extracao import extrair_protegido, ambiente_minimo, executar
from tests.test_web import cliente, entrar, enviar


def test_extracao_docx_real_em_subprocesso(tmp_path):
    from docx import Document
    documento = Document()
    documento.add_paragraph('Prova pública de Banco de Dados dia 20 na sala 5.')
    caminho = tmp_path / 'calendario.docx'
    documento.save(caminho)
    assert extrair_protegido(caminho) == [(None, 'Prova pública de Banco de Dados dia 20 na sala 5.')]


def test_extracao_pdf_real_em_subprocesso():
    caminho = Path(__file__).resolve().parents[1] / 'dados/turma_exemplo.pdf'
    paginas = extrair_protegido(caminho)
    assert paginas and any('Banco' in texto for _, texto in paginas)


def test_pdf_javascript_rejeitado(tmp_path):
    from pypdf import PdfWriter
    escritor = PdfWriter()
    escritor.add_blank_page(100, 100)
    escritor.add_js('app.alert("teste");')
    caminho = tmp_path / 'ativo.pdf'
    escritor.write(caminho)
    with pytest.raises(ErroIndexacao, match='ação'):
        extrair_protegido(caminho)


@pytest.mark.parametrize('nome,conteudo', [('word/vbaProject.bin', b'x'), ('../fora.xml', b'x'),
    ('word/embeddings/objeto.bin', b'x'), ('word/_rels/document.xml.rels', b'<Relationship TargetMode="External"/>'),
    ('word/extra.xml', b'<!DOCTYPE x [<!ENTITY a "b">]><x/>')])
def test_docx_ativo_ou_ambiguo_recusado(tmp_path, nome, conteudo):
    caminho = tmp_path / 'ativo.docx'
    with ZipFile(caminho, 'w') as arquivo:
        arquivo.writestr('word/document.xml', '<document/>')
        arquivo.writestr(nome, conteudo)
    with pytest.raises(ErroIndexacao):
        conferir_docx(caminho)


def test_segredos_nao_passam_no_ambiente_do_worker(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'sigilo')
    monkeypatch.setenv('MYSQL_SENHA', 'sigilo')
    monkeypatch.setenv('ADMIN_TOTP_SECRET', 'sigilo')
    assert not {'GEMINI_API_KEY','MYSQL_SENHA','ADMIN_TOTP_SECRET'} & ambiente_minimo().keys()


def test_parser_travado_tem_timeout_e_falha_sanitizada(tmp_path, monkeypatch):
    def travar(comando, **kwargs):
        assert kwargs['timeout'] == 20 and 'shell' not in kwargs
        raise subprocess.TimeoutExpired(comando, 20)
    monkeypatch.setattr(subprocess, 'run', travar)
    with pytest.raises(ErroIndexacao, match='limite de recursos'):
        executar(tmp_path / 'a.pdf', tmp_path / 'resultado.json')


@pytest.mark.parametrize('nome',['CON.txt','com1.pdf','aux.docx','a\u202e.txt','a\x7f.txt'])
def test_nome_invisivel_ou_reservado_recusado(cliente, nome):
    entrar(cliente)
    assert enviar(cliente, nome=nome).status_code == 422
