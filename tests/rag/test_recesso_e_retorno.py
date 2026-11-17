"""O recesso oficial e a volta às aulas são fatos distintos do mesmo calendário."""
import asyncio
from dataclasses import replace
from datetime import date
import pytest
from aplicacao.dominio.trecho_documento import TrechoDocumento
from aplicacao.servicos.recuperacao.calendario.relacoes import data_final, volta_seguinte
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.servicos.respostas.respostas_rag import interpretar
from tests.rag.test_respostas_por_curso import SeletorPrimeiro


@pytest.mark.parametrize('pergunta', [
    'quando começa as férias na fatec?',
    'quando começam as férias?',
    'quando acabam as férias?',
    'quando são as ferias da faculdade?',
    'quando voltam as aulas após as férias?',
    'quando é o recesso de julho?',
    'qual dia é o receso de julho?',
    'quando termina o recesso escolar?',
])
def test_ferias_inclui_recesso_oficial_e_inicio_das_aulas(base_pdf, pergunta):
    c = ConsultorRAG(base_pdf, SeletorPrimeiro(), limiar_similaridade=base_pdf.limiar_relevancia)
    r = asyncio.run(c.responder(pergunta))
    assert r.encontrou, r.texto
    assert 'Recesso oficial: de 10 a 25 de julho de 2026.' in r.texto
    assert 'Retorno às aulas: dia 3 de agosto de 2026' in r.texto
    assert '27 de julho' not in r.texto and '.pdf' not in r.texto
    assert {t.tipo_info for t in r.fontes} == {'recesso', 'retorno_aulas'}


def test_par_de_fatos_usa_a_mesma_fonte_e_versao(base_pdf):
    trechos = base_pdf.buscar('Quando começam as férias?', 12)
    assert len(trechos) == 2
    assert len({(t.arquivo, t.versao_id, t.grupo_resposta) for t in trechos}) == 1
    r = interpretar('{"status":"respondida","trechos":[2]}', trechos, 1)
    assert r.encontrou and len(r.fontes) == 2


def test_nao_deduz_ferias_de_dezembro_sem_intervalo_publicado(base_pdf):
    assert base_pdf.buscar('Quando são as férias de dezembro de 2026?', 12) == []


def test_nao_associa_outro_calendario_ou_inicio_do_semestre():
    r = TrechoDocumento('a.pdf', 1, '- De 10 a 25 de julho de 2026: Período de Recesso', versao_id='v1')
    aula = TrechoDocumento('b.pdf', 1, '- Dia 3 de agosto de 2026: Início das aulas', versao_id='v1')
    semestre = replace(aula, arquivo='a.pdf', texto='- Dia 27 de julho de 2026: Início do 2º Semestre')
    versao_antiga = replace(aula, arquivo='a.pdf', versao_id='antiga')
    assert volta_seguinte(r, [aula, semestre, versao_antiga]) is None
    assert volta_seguinte(r, [replace(aula, arquivo='a.pdf')]) is not None


def test_leitura_da_data_final_preserva_troca_de_ano():
    assert data_final('- De 20 de dezembro de 2026 a 10 de janeiro de 2027: Recesso') == date(2027, 1, 10)
    assert data_final('- Data a definir (julho de 2026): Evento') is None


def test_apresentacao_nao_omite_condicao_do_evento():
    from aplicacao.servicos.respostas.apresentacao.texto import texto_campo
    restrito = '- De 10 a 25 de julho de 2026: Período de Recesso apenas para docentes'
    assert texto_campo(restrito, 'recesso') == restrito
