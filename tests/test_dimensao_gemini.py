"""Exercite o contrato de dimensões da indexação e da consulta sem chave real."""
import json
import unittest

import httpx
import numpy as np
from infra.gemini_http import ClienteGemini, ErroGemini
from servicos.gemini import EmbeddingsGemini, vetor_validado


class DimensaoGemini(unittest.TestCase):
    def test_lote_e_consulta_preservam_prefixo_na_mesma_escala(self):
        curto = [3, 4] + [0] * 766
        completo = curto + [9] * 2304

        def resposta(req):
            corpo = json.loads(req.content)
            lote = req.url.path.endswith(':batchEmbedContents')
            pedidos = corpo['requests'] if lote else [corpo]
            for p in pedidos:
                self.assertEqual(p['embedContentConfig']['outputDimensionality'], 768)
            dados = {'embeddings': [{'values': completo}, {'values': curto}]} if lote else {'embedding': {'values': completo}}
            return httpx.Response(200, json=dados)

        api = ClienteGemini('teste', httpx.MockTransport(resposta))
        self.addCleanup(api.fechar)
        modelo = EmbeddingsGemini(api, 'gemini-embedding-001')
        matriz = modelo.codificar(['documento A', 'documento B'])
        self.assertEqual(matriz.shape, (2, 768))
        esperado = np.array([.6, .8] + [0] * 766)
        for vetor in [*matriz, modelo.consulta('pergunta')]:
            np.testing.assert_allclose(vetor, esperado, rtol=1e-6)

    def test_recusa_dados_invalidos_sem_expor_resposta(self):
        casos = [([1]*42, '42 dimensões'), ([], '0 dimensões'),
                 ([0]*768+[1]*2304, 'norma zero'), ([1]*768+[float('nan')]*2304, 'não finito'),
                 ([['privado']], 'unidimensional')]
        for values, motivo in casos:
            with self.subTest(motivo=motivo), self.assertRaisesRegex(ErroGemini, motivo):
                vetor_validado({'embedding': {'values': values}}, 'gemini-embedding-001')
        with self.assertRaisesRegex(ErroGemini, '3072 dimensões'):
            vetor_validado({'embedding': {'values': [1]*3072}}, 'outro-modelo')
        with self.assertRaisesRegex(ErroGemini, 'embedding.values'):
            vetor_validado({})
