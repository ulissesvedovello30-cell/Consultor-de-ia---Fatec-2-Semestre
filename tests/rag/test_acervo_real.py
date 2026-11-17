"""Recuperação factual dos três PDFs que acompanham esta entrega."""
import pytest
from aplicacao.servicos.acervo.documentos_reais import manifesto
from aplicacao.servicos.respostas.politica import PESSOAIS
from aplicacao.servicos.recuperacao.filtros_acervo import delimitar


@pytest.mark.parametrize('pergunta,pagina,texto', [
    ('Quando é o Hackathon?', 2, '27 e 28 de março de 2026'),
    ('Quando é a Aula Magna?', 1, '9 de fevereiro de 2026'),
    ('Quando começa o primeiro semestre de 2026?', 1, '4 de fevereiro de 2026'),
    ('Qual a duração do curso de IA?', 26, 'Mínimo de 02 anos (04 semestres)'),
    ('Qual a duração do curso de ESG?', 26, 'Máximo de 03 anos e 01 semestre (07 semestres)'),
    ('Qual a carga horária de IA?', 26, '2.000 horas'),
    ('Quais disciplinas tem IA?', 44, 'Linguagem de Programação I'),
])
def test_recupera_fato_do_pdf(base_pdf, pergunta, pagina, texto):
    candidatos = base_pdf.buscar(pergunta, 12)
    assert candidatos and candidatos[0].pagina == pagina
    assert texto in candidatos[0].texto
    assert candidatos[0].similaridade >= base_pdf.limiar_relevancia


def test_pdfs_reais_e_textos_institucionais_sem_exemplos(base_pdf):
    fontes = base_pdf.repositorio.listar()
    assert {f['nome'] for f in fontes} == {f['arquivo'] for f in manifesto()['fontes']}
    assert len(fontes) == 5 and sum(f['nome'].endswith('.pdf') for f in fontes) == 3
    assert all(not PESSOAIS.search(t.texto) for t in base_pdf._textos)
    assert all(t.pagina for t in base_pdf._textos if t.arquivo.endswith('.pdf'))


def test_eventos_gerais_tem_datas_e_nao_sao_ementas(base_pdf):
    trechos = base_pdf.buscar('Quais eventos estão no calendário da faculdade?', 12)
    texto = '\n'.join(t.texto for t in trechos)
    assert 'Hackathon' in texto and 'Aula Magna' in texto and 'março de 2026' in texto
    assert all('Calendario-Academico' in t.arquivo for t in trechos)


def test_cursos_gerais_nao_pedem_curso_para_listar_os_cursos(base_pdf):
    trechos = base_pdf.buscar('Quais cursos a Fatec oferece?', 12)
    assert {t.curso for t in trechos} == {'IA', 'ESG'}
    assert not delimitar('Quais cursos a Fatec oferece?', trechos)[1]
    assert all(t.pagina == 26 and '.....' not in t.texto for t in trechos)
    assert any('Inteligência Artificial' in t.texto for t in trechos)


def test_nao_mistura_ia_e_esg(base_pdf):
    assert all(t.curso != 'ESG' for t in base_pdf.buscar('Qual a duração de IA?', 12))
    assert all(t.curso != 'IA' for t in base_pdf.buscar('Qual a duração de ESG?', 12))


def test_fevereiro_nao_e_janeiro(base_pdf):
    texto = '\n'.join(t.texto for t in base_pdf._textos)
    assert 'Dia 28 de fevereiro de 2026 (sábado): Prazo final de matrículas de alunos ingressantes' in texto
    assert 'Dia 28 de janeiro de 2026 (quarta-feira): Prazo final de matrículas de alunos ingressantes' not in texto


def test_nao_inventa_data_de_prova_de_disciplina(base_pdf):
    trechos = base_pdf.buscar('Quando é a prova de Banco de Dados?', 12)
    assert not any('20/11/2026' in t.texto or '20 de novembro de 2026' in t.texto for t in trechos)


def test_inicio_de_aulas_nao_e_inicio_administrativo_do_semestre(base_pdf):
    trecho = base_pdf.buscar('Quando começam as aulas do segundo semestre de 2026?', 12)[0]
    assert 'Dia 3 de agosto de 2026' in trecho.texto
    assert 'Início das aulas' in trecho.texto


def test_eventos_respeitam_mes_e_ano_explicitos(base_pdf):
    eventos = base_pdf.buscar('Quais eventos estão no calendário em novembro de 2026?', 12)
    assert eventos and all('novembro de 2026' in t.texto.split(':', 1)[0] for t in eventos)
    assert base_pdf.buscar('Quais eventos estão no calendário de 2099?', 12) == []
