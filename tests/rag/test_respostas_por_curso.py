"""Perguntas por assunto e curso, incluindo os exemplos enviados pelo usuário."""
import asyncio
import json
import pytest
from aplicacao.core.chatbot import Chatbot
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG


class SeletorPrimeiro:
    def gerar(self, mensagens):
        return json.dumps({'status': 'respondida', 'trechos': [1]})


@pytest.fixture
def bot_por_curso(base_pdf):
    return Chatbot(ConsultorRAG(base_pdf, SeletorPrimeiro(), limiar_similaridade=base_pdf.limiar_relevancia))


@pytest.mark.parametrize('pergunta', [
    'quanto dura os cursos?',
    'no caso quanto dura cada curso? o de ia e o de esg?',
    'quanto tempo duram IA e ESG?',
    'queria saber quanto tempo dura cada um dos cursos',
    'qual é a duração de cada curso?',
    'em quantos anos termino os cursos de IA e ESG?',
    'a duração dos dois é igual?',
    'Quantos semestres têm os cursos?',
])
def test_duracao_informa_nomes_e_prazos_de_cada_curso(bot_por_curso, pergunta):
    resposta = asyncio.run(bot_por_curso.processar_mensagem('x', pergunta))
    assert resposta.sucesso, resposta.texto
    assert 'Gestão da Sustentabilidade Ambiental, Social e Governança Corporativa:' in resposta.texto
    assert 'Inteligência Artificial:' in resposta.texto
    esg, ia = resposta.texto.split('Inteligência Artificial:')
    assert '2 anos (4 semestres)' in esg and '3 anos e 1 semestre (7 semestres)' in esg
    assert '2 anos (4 semestres)' in ia and '3 anos (6 semestres)' in ia
    assert len(resposta.fontes) == 2 and '.pdf' not in resposta.texto


@pytest.mark.parametrize('pergunta,curso,nao_incluir', [
    ('Quanto dura o curso de IA?', 'Inteligência Artificial:', 'Governança Corporativa:'),
    ('quanto tempo dura o de inteligência artificial?', 'Inteligência Artificial:', 'Governança Corporativa:'),
    ('Qual a duração do curso de ESG?', 'Governança Corporativa:', 'Inteligência Artificial:'),
    ('Quanto dura o curso de Gestão da Sustentabilidade?', 'Governança Corporativa:', 'Inteligência Artificial:'),
    ('quantos anos dura I.A.?', 'Inteligência Artificial:', 'Governança Corporativa:'),
])
def test_nome_e_limites_ficam_ligados_ao_curso_pedido(bot_por_curso, pergunta, curso, nao_incluir):
    r = asyncio.run(bot_por_curso.processar_mensagem('x', pergunta))
    assert r.sucesso, r.texto
    assert curso in r.texto and nao_incluir not in r.texto
    assert len(r.fontes) == 1


def test_conversa_troca_curso_sem_reutilizar_ficha_anterior(bot_por_curso):
    q1 = asyncio.run(bot_por_curso.processar_mensagem('sessao', 'Quanto dura o curso de IA?'))
    q2 = asyncio.run(bot_por_curso.processar_mensagem('sessao', 'e o de ESG?'))
    q3 = asyncio.run(bot_por_curso.processar_mensagem('sessao', 'é presencial?'))
    assert q1.sucesso and q2.sucesso and q3.sucesso
    assert 'Inteligência Artificial:' in q1.texto and 'Governança Corporativa:' not in q1.texto
    assert 'Governança Corporativa:' in q2.texto and 'Inteligência Artificial:' not in q2.texto
    assert 'Governança Corporativa:' in q3.texto and 'presenciais' in q3.texto


def test_consulta_coletiva_nao_herda_um_unico_curso(bot_por_curso):
    asyncio.run(bot_por_curso.processar_mensagem('s', 'Quanto dura o curso de IA?'))
    r = asyncio.run(bot_por_curso.processar_mensagem('s', 'quanto dura cada curso?'))
    assert r.sucesso and {t.curso for t in r.fontes} == {'IA', 'ESG'}


def test_curso_desconhecido_nao_e_trocado_por_ia_ou_esg(base_pdf):
    candidatos = base_pdf.buscar('Quanto dura o curso de Medicina?', 12)
    assert not candidatos or max(t.similaridade for t in candidatos) < base_pdf.limiar_relevancia


def test_ressalva_apos_prazo_maximo_nao_e_descartada():
    from aplicacao.dominio.trecho_documento import TrechoDocumento
    from aplicacao.servicos.recuperacao.planejamento.fichas import recortar_ficha
    from aplicacao.servicos.respostas.apresentacao.texto import texto_duracao
    fonte = TrechoDocumento('ppc.txt', None,
        'Prazo de integralização\nMínimo de 02 anos (04 semestres)\nMáximo de 03 anos\n(06 semestres)\nExceto quando houver regra específica publicada.', curso='IA')
    trecho = recortar_ficha(fonte, 'duracao')
    assert trecho is not None
    texto = texto_duracao(trecho.texto)
    assert '6 semestres' in texto and 'Exceto quando houver regra específica publicada.' in texto
