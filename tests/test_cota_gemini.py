"""Cota temporária e retomada da carga inicial com transporte local."""
import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import httpx
import montagem
from infra.gemini_http import ClienteGemini, ErroGemini
from servicos.prazo import FIM
import time


def cota(diaria=False):
    """Construa um 429 de teste sem usar a API externa."""
    detalhes = [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '9s'}]
    if diaria:
        detalhes.append({'@type': 'type.googleapis.com/google.rpc.QuotaFailure',
                         'violations': [{'quotaId': 'RequestsPerDayPerProject'}]})
    return httpx.Response(429, headers={'Retry-After': '7'}, json={'error': {'details': detalhes}})


class Cotas(unittest.TestCase):
    def test_prazo_e_limite_de_tentativas(self):
        api = ClienteGemini('teste', httpx.MockTransport(lambda _: cota()))
        self.addCleanup(api.fechar)
        with patch('infra.cota_gemini.sleep') as pausa:
            with self.assertRaisesRegex(ErroGemini, 'HTTP 429'):
                api.chamar('modelo', 'batchEmbedContents', {})
            self.assertEqual([x.args[0] for x in pausa.call_args_list], [9, 10, 20, 40, 80, 120])
            pausa.reset_mock()
            token = FIM.set(time.monotonic() + 1)
            try:
                with self.assertRaisesRegex(ErroGemini, 'HTTP 429'):
                    api.chamar('modelo', 'batchEmbedContents', {})
                pausa.assert_not_called()
            finally:
                FIM.reset(token)

    def test_inicializacao_com_cota_e_retomada(self):
        vistos = set()
        respostas = []
        def receber(req):
            pedidos = json.loads(req.content)['requests']
            respostas.append(len(pedidos))
            if len(respostas) == 2:
                return cota(True)
            if len(respostas) == 3:
                return cota()
            self.assertNotIn(req.content, vistos, 'Um lote já concluído foi repetido.')
            vistos.add(req.content)
            return httpx.Response(200, json={'embeddings': [{'values': [1]+[0]*767} for _ in pedidos]})

        def cliente(chave):
            return ClienteGemini(chave, httpx.MockTransport(receber))
        with TemporaryDirectory() as pasta:
            banco = str(Path(pasta)/'acervo.sqlite3')
            with patch.object(montagem.config, 'BUSCA_ACERVO', 'gemini'), patch.object(montagem.config, 'SQLITE_CAMINHO', banco), patch.object(
                montagem.config, 'GEMINI_API_KEY', 'teste'), patch.object(
                montagem, 'ClienteGemini', cliente), patch('infra.cota_gemini.sleep') as pausa:
                with self.assertRaisesRegex(ErroGemini, '429.*diária'), montagem.abrir_chatbot():
                    pass
                self.assertEqual(len(respostas), 2)
                pausa.assert_not_called()
                with sqlite3.connect(banco) as db:
                    self.assertEqual(db.execute('select count(*) from rag_lote_inicial').fetchone()[0], 1)
                    self.assertEqual(db.execute('select count(*) from rag_inicializacao').fetchone()[0], 0)
                with montagem.abrir_chatbot() as (_, base):
                    self.assertEqual(len(base.repositorio.listar()), 3)
                pausa.assert_called_once_with(9)
                with sqlite3.connect(banco) as db:
                    self.assertEqual(db.execute('select count(*) from rag_lote_inicial').fetchone()[0], 0)
                n = len(respostas)
                with montagem.abrir_chatbot(): pass
                self.assertEqual(len(respostas), n)


class EsperaProlongada(unittest.TestCase):
    def test_aguarda_terceira_resposta_que_pede_49s(self):
        """Não descarte a terceira espera por ter esgotado duas repetições."""
        sequencia = iter([7, 7, 49, None])
        def receber(req):
            atraso = next(sequencia)
            if atraso is None:
                return httpx.Response(200, json={'embeddings': []})
            return httpx.Response(429, json={'error': {'details': [{'retryDelay': f'{atraso}s'}]}})
        api = ClienteGemini('teste', httpx.MockTransport(receber))
        self.addCleanup(api.fechar)
        with patch('infra.cota_gemini.sleep') as pausa:
            self.assertEqual(api.chamar('modelo', 'batchEmbedContents', {}), {'embeddings': []})
            self.assertEqual([x.args[0] for x in pausa.call_args_list], [7, 10, 49])

    def test_limite_zero_e_diagnostico_sem_corpo_bruto(self):
        """Identifique limite zero e preserve o sigilo da mensagem remota."""
        corpo = {'error': {'message': 'segredo limit: 0, model: privado',
            'details': [{'violations': [{'quotaId': 'EmbedContentRequestsPerMinute',
                                        'quotaValue': '0'}]}]}}
        api = ClienteGemini('teste', httpx.MockTransport(lambda req: httpx.Response(429, json=corpo)))
        self.addCleanup(api.fechar)
        with patch('infra.cota_gemini.sleep') as pausa:
            with self.assertRaisesRegex(ErroGemini, 'limite zero.*EmbedContentRequestsPerMinute') as exc:
                api.chamar('modelo', 'batchEmbedContents', {})
            pausa.assert_not_called()
        self.assertNotIn('segredo', str(exc.exception))
        self.assertNotIn('privado', str(exc.exception))

    def test_detalhes_malformados_nao_quebram_diagnostico(self):
        """Mantenha o erro de cota mesmo quando os detalhes não têm o formato esperado."""
        from infra.cota_gemini import resumo_cotas
        for corpo in ({}, {'error': None}, {'error': {'details': [{'violations': 3}]}}):
            self.assertIn('não identificou', resumo_cotas(httpx.Response(429, json=corpo)))
