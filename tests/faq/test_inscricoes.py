"""Diferencie edição, previsão, prazo prorrogado e pagamento do vestibular."""
import asyncio
import pytest
from aplicacao.core.chatbot import Chatbot
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from tests.faq.test_perguntas_frequentes import SeletorControlado


@pytest.mark.parametrize('pergunta', ['Qual o período para inscrições no Vestibular?',
    'qnd abre incricoes vesitbular', 'quando posso me inscrever no vestibular'])
def test_periodo_geral_explica_ingresso_e_nao_confunde_prova(base_pdf, pergunta):
    bot = Chatbot(ConsultorRAG(base_pdf, SeletorControlado(), limiar_similaridade=base_pdf.limiar_relevancia))
    resposta = asyncio.run(bot.processar_mensagem('inscricoes', pergunta))
    assert resposta.sucesso and 'ingresso em fevereiro' in resposta.texto and 'ingresso em agosto' in resposta.texto
    assert 'Ingresso no 2º semestre de 2026:' in resposta.texto and 'Período previsto' in resposta.texto
    assert 'Ingresso no 1º semestre de 2027:' in resposta.texto and '16 de novembro de 2026' in resposta.texto
    assert '6 de novembro de 2026' not in resposta.texto.replace('16 de novembro de 2026', '')
    assert '13 de dezembro' not in resposta.texto


@pytest.mark.parametrize('pergunta', ['inscricoes vestibular 2027', 'qual prazo do vestibular para ingresso no primeiro semestre de 2027'])
def test_ano_do_ingresso_nao_filtra_ano_da_inscricao(base_pdf, pergunta):
    pergunta = pergunta.replace('qual prazo do vestibular', 'qual prazo de inscrições do vestibular')
    trechos = base_pdf.buscar(pergunta, 12)
    assert len(trechos) == 1 and trechos[0].arquivo == 'Atualizacao_Vestibular_1SEM2027.txt'
    assert '14 de setembro a 16 de novembro de 2026' in trechos[0].texto
    assert 'Prazo prorrogado' in trechos[0].texto


def test_ausencia_de_edicao_nao_vira_periodicidade_generica(base_pdf):
    assert base_pdf.buscar('quando sao as inscricoes do vestibular de 2099', 12) == []


def test_pagamento_nao_reabre_periodo_de_inscricao(base_pdf):
    trechos = base_pdf.buscar('qual prazo de pagamento da taxa do vestibular', 12)
    assert len(trechos) == 1 and ': Pagamento da taxa' in trechos[0].texto
    assert '17 de novembro de 2026' in trechos[0].texto and 'inscrições feitas até 16 de novembro' in trechos[0].texto


def test_consulta_atual_nao_recupera_edicao_antiga_como_se_estivesse_aberta(base_pdf):
    bot = Chatbot(ConsultorRAG(base_pdf, SeletorControlado(), limiar_similaridade=base_pdf.limiar_relevancia))
    resposta = asyncio.run(bot.processar_mensagem('agora', 'posso me inscrever agora no vestibular'))
    assert resposta.sucesso and '16 de novembro de 2026' in resposta.texto
    assert 'Ingresso no 2º semestre de 2026' not in resposta.texto
    assert not resposta.texto.startswith('Sim')
