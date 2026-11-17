"""Perguntas informais, flexões e recortes contra os PDFs reais."""
import pytest
from aplicacao.servicos.respostas.politica import validar_pergunta
from aplicacao.servicos.recuperacao.filtros_acervo import delimitar


@pytest.mark.parametrize('pergunta,esperado', [
    ('quando é as férias na fatec?', '10 a 25 de julho de 2026'),
    ('Quando são as férias?', '10 a 25 de julho de 2026'),
    ('Qual dia é o receso de julho?', '10 a 25 de julho de 2026'),
    ('Quando é o recesso escolar?', '10 a 25 de julho de 2026'),
    ('quando é o vestibular da fatec?', 'Previsão da realização do exame'),
    ('Em que dia vai ser a prova do vestibular?', 'Previsão da realização do exame'),
    ('Quando começam as inscrições pro vestibular?', '7 de abril a 1 de junho de 2026'),
    ('Quais graduações vocês têm?', 'Inteligência Artificial'),
    ('Quais cursos a Fatec oferece?', 'Inteligência Artificial'),
    ('Eu queria saber por quanto tempo vou estudar IA', 'Mínimo de 02 anos'),
    ('Quais são os feriados da faculdade?', 'feriado'),
    ('Quando acaba o segundo semestre?', '14 de dezembro de 2026'),
])
def test_perguntas_informais_recuperam_evidencia(base_pdf, pergunta, esperado):
    validar_pergunta(pergunta)
    candidatos = base_pdf.buscar(pergunta, 12)
    texto = '\n'.join(t.texto for t in candidatos)
    assert candidatos and esperado.casefold() in texto.casefold()
    assert max(t.similaridade for t in candidatos) >= base_pdf.limiar_relevancia
    assert not delimitar(pergunta, candidatos)[1]


def test_cursos_veem_do_corpo_e_sao_nomes_completos(base_pdf):
    trechos = base_pdf.buscar('Quais cursos a Fatec oferece?', 12)
    assert {t.pagina for t in trechos} == {26}
    assert {t.texto for t in trechos} == {'Inteligência Artificial',
        'Gestão da Sustentabilidade Ambiental, Social e Governança Corporativa'}


def test_vestibular_nao_recupera_matricula_ou_chamada(base_pdf):
    candidatos = base_pdf.buscar('quando é o vestibular da fatec?', 12)
    assert len(candidatos) == 2
    assert all('exame' in t.texto.casefold() for t in candidatos)
    assert any('Horário confirmado' in t.texto for t in candidatos)
    assert not any('Chamada' in t.texto or 'Matrícula' in t.texto for t in candidatos)


def test_inscricao_nao_se_confunde_com_isencao_de_taxa(base_pdf):
    trechos = base_pdf.buscar('Quando começam as inscrições pro vestibular?', 12)
    assert trechos and all('isenção' not in t.texto and 'redução' not in t.texto for t in trechos)
    isencao = base_pdf.buscar('Qual o período de isenção da taxa do vestibular?', 12)
    assert isencao and all('isenção' in t.texto for t in isencao)


def test_ferias_nao_fabrica_intervalo_que_nao_existe(base_pdf):
    assert base_pdf.buscar('Quando são as férias de dezembro de 2026?', 12) == []


def test_pergunta_sem_assunto_nao_ganha_evidencia_por_aproximacao(base_pdf):
    candidatos = base_pdf.buscar('quasar zxyw inexistente', 12)
    assert not candidatos or max(t.similaridade for t in candidatos) < base_pdf.limiar_relevancia


def test_ano_de_ingresso_nao_e_confundido_com_data_do_exame(base_pdf):
    exame = base_pdf.buscar('Quando é o vestibular do primeiro semestre de 2027?', 12)
    assert len(exame) == 1 and '13 de dezembro de 2026' in exame[0].texto
    inscricoes = base_pdf.buscar('Qual o período de inscrições para o vestibular de 2027?', 12)
    assert len(inscricoes) == 1 and '14 de setembro a 16 de novembro de 2026' in inscricoes[0].texto


def test_parafrases_curriculares_sem_modelo_local(base_pdf):
    assert base_pdf.buscar('O que vou aprender no curso de IA?', 12)[0].pagina == 44
    assert base_pdf.buscar('Quantos semestres tem o curso de IA?', 12)[0].pagina == 26
    assert 'presenciais' in base_pdf.buscar('Qual é a modalidade do curso de IA?', 12)[0].texto
    assert 'assíncronas' in base_pdf.buscar('Qual é a modalidade do curso de IA?', 12)[0].texto
