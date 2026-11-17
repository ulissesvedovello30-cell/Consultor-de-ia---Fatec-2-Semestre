"""Exercite as perguntas da secretaria com o mesmo acervo usado pela aplicação."""
import asyncio
import json
import pytest
from aplicacao.core.chatbot import Chatbot
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG


class SeletorControlado:
    """Isole o contrato de seleção do Gemini para testar recuperação e apresentação."""

    def gerar(self, mensagens):
        return json.dumps({'status': 'respondida', 'trechos': [1]})


@pytest.fixture
def bot(base_pdf):
    return Chatbot(ConsultorRAG(base_pdf, SeletorControlado(), limiar_similaridade=base_pdf.limiar_relevancia))


@pytest.mark.parametrize('pergunta,esperados', [
    ('Quais cursos a Fatec oferece?', ['Tecnologia em Inteligência Artificial', 'Governança Corporativa']),
    ('q cursos vcs oferecem', ['Tecnologia em Inteligência Artificial', 'Governança Corporativa']),
    ('quais curss tem na fatec', ['Tecnologia em Inteligência Artificial', 'Governança Corporativa']),
    ('Quais graduações vocês têm?', ['Inteligência Artificial', 'Governança Corporativa']),
    ('Qual a mensalidade?', ['gratuitos', 'sem mensalidade', 'taxa de inscrição']),
    ('qual a menslidade dos cusros', ['gratuitos', 'taxa de inscrição']),
    ('qual a mensaliddade', ['gratuitos', 'taxa de inscrição']),
    ('é gratis', ['gratuitos', 'sem mensalidade']),
    ('quanto custa estudar ai', ['gratuitos', 'taxa de inscrição']),
    ('a fatec cobra mensalidade e taxa de inscrição', ['sem mensalidade', 'taxa de inscrição']),
    ('Qual horário dos cursos?', ['Inteligência Artificial:', '7h40 às 13h', 'Governança Corporativa:', '19h às 22h30']),
    ('qual horaro das aulas', ['Inteligência Artificial:', '7h40 às 13h', '19h às 22h30']),
    ('que horas começa e acaba', ['Inteligência Artificial:', '7h40 às 13h', '19h às 22h30']),
    ('qual o horario do curso', ['7h40 às 13h', '19h às 22h30']),
    ('As aulas são presenciais?', ['presenciais', 'algumas disciplinas assíncronas']),
    ('as aulas sao prezenciais', ['presenciais', 'algumas disciplinas assíncronas']),
    ('é ead?', ['presenciais', 'algumas disciplinas assíncronas']),
    ('tem aula online', ['presenciais', 'algumas disciplinas assíncronas']),
    ('os cursos são 100% online', ['presenciais', 'algumas disciplinas assíncronas']),
    ('precisa ir na faculdade para as aulas', ['presenciais', 'algumas disciplinas assíncronas']),
    ('Como consigo acessar a grade curricular de cada curso?', ['https://fatecrioclaro.cps.sp.gov.br/ia/', 'https://fatecrioclaro.cps.sp.gov.br/esg/']),
    ('onde vejo a grade', ['https://fatecrioclaro.cps.sp.gov.br/ia/', 'https://fatecrioclaro.cps.sp.gov.br/esg/']),
    ('como acesso a grdae curricular', ['https://fatecrioclaro.cps.sp.gov.br/ia/', 'https://fatecrioclaro.cps.sp.gov.br/esg/']),
    ('Quanto tempo de duração é o curso?', ['Inteligência Artificial:', 'Governança Corporativa:', '2 anos (4 semestres)']),
    ('qnt tempo dura', ['Inteligência Artificial:', 'Governança Corporativa:', '2 anos (4 semestres)']),
    ('qual a duraçao dos curss', ['Inteligência Artificial:', 'Governança Corporativa:', '2 anos (4 semestres)']),
    ('Os cursos são considerados de nível superior ou técnico?', ['nível superior', 'cursos superiores de tecnologia']),
    ('é superior ou tecnico', ['nível superior', 'cursos superiores de tecnologia']),
    ('esses cursos sao tecnicos', ['nível superior', 'cursos superiores de tecnologia']),
    ('qual o horario e a mensalidade dos cursos', ['7h40 às 13h', '19h às 22h30', 'sem mensalidade']),
])
def test_variacoes_sem_curso_ou_pontuacao(bot, pergunta, esperados):
    resposta = asyncio.run(bot.processar_mensagem('variacao', pergunta))
    assert resposta.sucesso, resposta.texto
    assert all(t in resposta.texto for t in esperados), resposta.texto
    assert all(t not in resposta.texto for t in ['Assunto:', 'Pergunta:', 'Resposta:', 'FAQ_secretaria.txt'])
    assert resposta.fontes and 'Informe curso' not in resposta.texto


@pytest.mark.parametrize('pergunta,curso,presente,ausente', [
    ('Qual o horário de IA?', 'IA', '7h40 às 13h', '19h às 22h30'),
    ('qual horaro de inteligência artifical', 'IA', '7h40 às 13h', '19h às 22h30'),
    ('qual o horario de ESG?', 'ESG', '19h às 22h30', '7h40 às 13h'),
    ('onde vejo a grade de ESG', 'ESG', '/esg/', '/ia/'),
    ('IA é presencial?', 'IA', 'assíncronas', 'Governança Corporativa:'),
])
def test_curso_especifico_nao_mistura_outra_ficha(bot, pergunta, curso, presente, ausente):
    resposta = asyncio.run(bot.processar_mensagem('curso', pergunta))
    assert resposta.sucesso and presente in resposta.texto and ausente not in resposta.texto
    assert {t.curso for t in resposta.fontes} == {curso}


def test_contexto_troca_curso_e_preserva_novo_assunto(bot):
    primeira = asyncio.run(bot.processar_mensagem('conversa', 'qual horario de IA'))
    segunda = asyncio.run(bot.processar_mensagem('conversa', 'e o de ESG'))
    terceira = asyncio.run(bot.processar_mensagem('conversa', 'é ead'))
    assert '7h40 às 13h' in primeira.texto and '19h às 22h30' in segunda.texto
    assert '7h40' not in segunda.texto and 'Governança Corporativa:' in terceira.texto
    assert 'assíncronas' in terceira.texto


def test_aulas_a_distancia_nao_recebem_um_sim_enganoso(bot):
    resposta = asyncio.run(bot.processar_mensagem('ead', 'o curso é totalmente online?'))
    assert resposta.sucesso and 'presenciais' in resposta.texto
    assert not resposta.texto.startswith('Sim')
