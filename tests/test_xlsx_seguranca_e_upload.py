"""XLSX passa pelas mesmas defesas do DOCX: inspeção do pacote, extração isolada e upload autenticado."""
from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from dominio.erros import ErroIndexacao
from seguranca.arquivos import conferir_xlsx
from seguranca.extracao import extrair_protegido
from tests.test_planilha import criar_horario
from tests.test_web import cliente, entrar, enviar
from web.uploads import validar_conteudo, validar_nome


def planilha_bytes():
    pasta = Workbook()
    pasta.active.append(['Evento', 'Data'])
    pasta.active.append(['Feira de Projetos', '05/12/2026'])
    saida = BytesIO()
    pasta.save(saida)
    return saida.getvalue()


def zip_xlsx(tmp_path, **partes):
    """XLSX mínimo com o arquivo principal e mais as partes pedidas (nome -> conteúdo)."""
    caminho = tmp_path / 'ativo.xlsx'
    with ZipFile(caminho, 'w') as arquivo:
        arquivo.writestr('xl/workbook.xml', '<workbook/>')
        for nome, conteudo in partes.items():
            arquivo.writestr(nome.replace('__', '/'), conteudo)
    return caminho


def test_xlsx_gerado_pelo_excel_passa_na_inspecao(tmp_path):
    criar_horario(tmp_path / 'horario.xlsx')

    conferir_xlsx(tmp_path / 'horario.xlsx')
    assert extrair_protegido(tmp_path / 'horario.xlsx')


@pytest.mark.parametrize('nome,conteudo', [
    ('xl__vbaProject.bin', b'x'),
    ('xl__externalLinks__externalLink1.xml', b'<externalLink/>'),
    ('xl__embeddings__objeto.bin', b'x'),
    ('xl__activeX__activeX1.xml', b'<x/>'),
    ('xl__connections.xml', b'<connections/>'),
    ('xl___rels__workbook.xml.rels', b'<Relationship TargetMode="External"/>'),
    ('xl__extra.xml', b'<!DOCTYPE x [<!ENTITY a "b">]><x/>'),
    ('..__fora.xml', b'x'),
])
def test_xlsx_ativo_externo_ou_ambiguo_e_recusado(tmp_path, nome, conteudo):
    with pytest.raises(ErroIndexacao):
        conferir_xlsx(zip_xlsx(tmp_path, **{nome: conteudo}))


def test_xlsx_sem_arquivo_principal_ou_que_nao_e_zip_e_recusado(tmp_path):
    sem_principal = tmp_path / 'sem.xlsx'
    with ZipFile(sem_principal, 'w') as arquivo:
        arquivo.writestr('word/document.xml', '<document/>')  # é um DOCX renomeado
    falso = tmp_path / 'falso.xlsx'
    falso.write_bytes(b'texto comum')

    for caminho in (sem_principal, falso):
        with pytest.raises(ErroIndexacao, match='XLSX'):
            conferir_xlsx(caminho)


def test_xlsx_com_expansao_absurda_e_recusado(tmp_path):
    caminho = tmp_path / 'bomba.xlsx'
    with ZipFile(caminho, 'w') as arquivo:
        arquivo.writestr('xl/workbook.xml', '<workbook/>')
        for i in range(3001):
            arquivo.writestr(f'xl/p{i}.txt', 'x')

    with pytest.raises(ErroIndexacao, match='excede'):
        conferir_xlsx(caminho)


def test_nome_e_conteudo_xlsx_sao_validados_no_upload(tmp_path):
    assert validar_nome('Horario Curso IA.xlsx')
    (tmp_path / 'ok.xlsx').write_bytes(planilha_bytes())
    validar_conteudo(tmp_path / 'ok.xlsx')
    (tmp_path / 'docx_disfarcado.xlsx').write_bytes(b'nao e zip')
    with pytest.raises(ErroIndexacao, match='XLSX'):
        validar_conteudo(tmp_path / 'docx_disfarcado.xlsx')


def test_administrador_publica_xlsx_e_o_chat_responde_com_a_fonte(cliente):
    entrar(cliente)
    envio = cliente.post('/api/admin/documentos', params={'nome': 'eventos.xlsx', 'publico': 'true'}, content=planilha_bytes())
    assert envio.status_code == 200, envio.text

    resposta = cliente.post('/api/chat', json={'texto': 'Quando é a Feira de Projetos?'}).json()
    assert resposta['sucesso'] and '05/12/2026' in resposta['texto']
    assert 'eventos.xlsx' in resposta['texto'] or resposta['fontes'][0]['nome'] == 'eventos.xlsx'


def test_xlsx_falso_e_visitante_sem_login_nao_publicam(cliente):
    sem_login = cliente.post('/api/admin/documentos', params={'nome': 'a.xlsx', 'publico': 'true'}, content=planilha_bytes())
    assert sem_login.status_code == 401
    entrar(cliente)
    assert enviar(cliente, texto='isto nao e uma planilha', nome='falso.xlsx').status_code == 422
    assert cliente.get('/api/admin/documentos').json() == []
