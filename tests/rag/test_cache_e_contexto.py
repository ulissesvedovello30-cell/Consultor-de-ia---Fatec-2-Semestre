"""Validade das seleções, invalidação documental e preservação de ressalvas."""
import asyncio
import json
from dataclasses import replace
import pytest
from aplicacao.dominio.trecho_documento import TrechoDocumento
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.servicos.respostas.otimizacao.cache import CacheSelecoes, chave_selecao
from aplicacao.servicos.respostas.otimizacao.contexto import organizar_contexto


class GeradorContado:
    def __init__(self):
        self.chamadas, self.insuficiente = 0, False

    def gerar(self, mensagens):
        self.chamadas += 1
        return json.dumps({'status': 'insuficiente' if self.insuficiente else 'respondida',
                           'trechos': [] if self.insuficiente else [1]})


class BaseMutavel:
    def __init__(self):
        self.trecho = TrechoDocumento('aviso.txt', 1, 'A biblioteca abre às oito horas.', 1, versao_id='v1')

    def buscar(self, pergunta, k):
        return [self.trecho] if self.trecho else []


def test_cache_reutiliza_so_mesma_pergunta_e_versao():
    base, gerador = BaseMutavel(), GeradorContado()
    consultor = ConsultorRAG(base, gerador)
    pergunta = 'Qual o horário da biblioteca?'
    assert asyncio.run(consultor.responder(pergunta)).encontrou
    assert asyncio.run(consultor.responder(pergunta)).encontrou and gerador.chamadas == 1
    base.trecho = replace(base.trecho, texto='A biblioteca abre às nove horas.', versao_id='v2')
    assert 'nove' in asyncio.run(consultor.responder(pergunta)).texto
    assert gerador.chamadas == 2
    base.trecho = None
    assert not asyncio.run(consultor.responder(pergunta)).encontrou


def test_resposta_insuficiente_nao_fica_em_cache():
    base, gerador = BaseMutavel(), GeradorContado()
    gerador.insuficiente = True
    consultor = ConsultorRAG(base, gerador)
    for _ in range(2):
        assert not asyncio.run(consultor.responder('Qual o horário da biblioteca?')).encontrou
    assert gerador.chamadas == 2


def test_expiracao_e_capacidade_do_cache():
    agora = [0]
    cache = CacheSelecoes(capacidade=2, validade=10, relogio=lambda: agora[0])
    for chave in ['a', 'b', 'c']:
        cache.guardar(chave, chave)
    assert cache.obter('a') is None and cache.obter('b') == 'b'
    agora[0] = 11
    cache.expirar()
    assert cache.obter('b') is None and cache.obter('c') is None


def test_chave_muda_com_metadados_e_nao_guarda_pergunta():
    t = BaseMutavel().trecho
    a = chave_selecao('Qual o horário?', [t])
    b = chave_selecao('Qual o horário?', [replace(t, curso='IA')])
    assert a != b and len(a) == 64 and 'horário' not in a


def test_contexto_nao_remove_negacao_ou_corta_trechos():
    t = BaseMutavel().trecho
    negativo = replace(t, texto='A biblioteca não abre às oito horas.')
    resultado = organizar_contexto([t, t, negativo])
    assert resultado == [t, negativo]
    assert organizar_contexto([t], caracteres=1) == []


def test_variacoes_estruturadas_equivalentes_reutilizam_selecao(base_pdf):
    gerador = GeradorContado()
    c = ConsultorRAG(base_pdf, gerador, limiar_similaridade=base_pdf.limiar_relevancia)
    a = asyncio.run(c.responder('quanto dura os cursos?'))
    b = asyncio.run(c.responder('no caso quanto dura cada curso? o de ia e o de esg?'))
    assert a.encontrou and b.encontrou and a.texto == b.texto
    assert gerador.chamadas == 1


def test_cache_nao_descarta_qualificador_desconhecido(base_pdf):
    trechos = base_pdf.buscar('Quanto dura o curso de IA?', 12)
    simples = chave_selecao('Quanto dura o curso de IA?', trechos)
    qualificada = chave_selecao('Quanto dura o curso de IA para transferidos?', trechos)
    assert simples != qualificada
