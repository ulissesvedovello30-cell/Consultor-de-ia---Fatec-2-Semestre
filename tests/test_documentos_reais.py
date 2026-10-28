"""Os documentos reais da pasta documentos/ (calendário e horário) entram na demonstração sem Gemini."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from debug_web import PASTA_DOCUMENTOS, documentos_da_pasta, montar_demo
from seguranca.extracao import extrair_protegido
from servicos.politica import validar_documento

pytestmark = pytest.mark.skipif(not documentos_da_pasta(), reason='pasta documentos/ vazia')


@pytest.fixture(scope='module')
def demo():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    yield montar_demo(engine)
    engine.dispose()


def perguntar(demo, pergunta):
    bot, _ = demo
    return asyncio.run(bot.processar_mensagem(f'teste-{pergunta}', pergunta))


def test_todos_os_documentos_passam_na_extracao_protegida_e_no_filtro_de_privacidade():
    for caminho in documentos_da_pasta():
        paginas = extrair_protegido(caminho)
        assert paginas
        for _, texto in paginas:
            validar_documento(texto)


def test_demo_indexa_o_calendario_e_o_horario(demo):
    _, base = demo
    nomes = {t.arquivo for t in base._indice[0]}

    assert any(n.startswith('Calendário') for n in nomes) and any(n.startswith('Horario') for n in nomes)
    assert base.total_trechos > 150


@pytest.mark.parametrize('pergunta,esperado', [
    ('Quando começam as aulas do 2º semestre de 2026?', 'Dia 3 de agosto de 2026 (segunda-feira): Início das aulas do 2º Semestre Letivo'),
    ('Quando termina o 1º semestre letivo?', 'Dia 27 de junho de 2026 (sábado): Término das aulas do 1º Semestre Letivo'),
    ('Quando é o recesso escolar em julho?', 'De 10 a 25 de julho de 2026: Período de Recesso'),
    ('Que dia é o Hackathon?', 'Dias 27 e 28 de março de 2026: Hackathon'),
    ('Qual o horário de Mineração de Dados?', '2º semestre, sexta-feira, das 7h40 às 9h20: Mineração de Dados. Professor(a): Angela Rosa Locateli de Godoy'),
    ('Quem é o professor de Aprendizado de Máquina I?', 'Aprendizado de Máquina I. Professor(a): Julio Cesar de Lemos'),
])
def test_perguntas_sobre_os_documentos_reais(demo, pergunta, esperado):
    resposta = perguntar(demo, pergunta)

    assert resposta.sucesso and esperado in resposta.texto
    assert resposta.fontes


def test_evento_de_fim_de_fevereiro_nao_foi_para_janeiro(demo):
    _, base = demo
    textos = [t.texto for t in base._indice[0]]

    assert any('Dia 28 de fevereiro de 2026 (sábado): Prazo final de matrículas de alunos ingressantes' in t for t in textos)
    assert not any('de janeiro de 2026' in t and 'Fechamento do sistema de matrícula remota' in t for t in textos)


def test_pergunta_fora_do_assunto_continua_recusada(demo):
    assert not perguntar(demo, 'Qual a cor das girafas azuis?').sucesso


def test_pasta_so_lista_formatos_aceitos_e_ignora_temporarios(tmp_path):
    for nome in ('a.pdf', 'b.xlsx', 'c.docx', 'd.txt', 'e.csv', '~$f.docx', 'g.exe'):
        (tmp_path / nome).write_bytes(b'x')
    (tmp_path / 'subpasta.pdf').mkdir()

    assert [c.name for c in documentos_da_pasta(tmp_path)] == ['a.pdf', 'b.xlsx', 'c.docx', 'd.txt']
    assert documentos_da_pasta(tmp_path / 'nao_existe') == []
    assert PASTA_DOCUMENTOS.name == 'documentos'


def test_expandir_troca_pastas_pelos_documentos_e_mantem_arquivos(tmp_path):
    from servicos.pasta import expandir
    (tmp_path / 'pasta').mkdir()
    for nome in ('pasta/a.pdf', 'pasta/b.csv', 'solto.docx'):
        (tmp_path / nome).write_bytes(b'x')

    assert [c.name for c in expandir([tmp_path / 'pasta', tmp_path / 'solto.docx'])] == ['a.pdf', 'solto.docx']
