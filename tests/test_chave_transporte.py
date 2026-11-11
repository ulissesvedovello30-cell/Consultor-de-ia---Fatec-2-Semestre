"""Validação do cabeçalho de autenticação sem chamadas externas."""
import unittest
import httpx
from infra.gemini_http import ClienteGemini, ErroGemini, chave_gemini


class ChaveTransporte(unittest.TestCase):
    def test_rotulo_e_chave_limpa_geram_mesmo_cabecalho(self):
        for valor in ('AQ.teste-local', 'API do gemini: AQ.teste-local'):
            def receber(req):
                self.assertEqual(req.headers['x-goog-api-key'], 'AQ.teste-local')
                return httpx.Response(200, json={'models': []})
            with_cliente = ClienteGemini(valor, httpx.MockTransport(receber))
            try:
                self.assertEqual(with_cliente.modelos(), {'models': []})
            finally:
                with_cliente.fechar()

    def test_recusa_vazio_espacos_e_controles(self):
        for valor in ('', 'API do gemini: ', 'abc def', 'abc\x00def', 'algo\nsegredo'):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                chave_gemini(valor)

    def test_400_distingue_chave_sem_expor_resposta(self):
        erro = {'error': {'message': 'texto confidencial', 'status': 'INVALID_ARGUMENT',
                          'details': [{'reason': 'API_KEY_INVALID'}]}}
        cliente = ClienteGemini('teste', httpx.MockTransport(lambda r: httpx.Response(400, json=erro)))
        self.addCleanup(cliente.fechar)
        with self.assertRaisesRegex(ErroGemini, 'HTTP 400.*GEMINI_API_KEY') as exc:
            cliente.modelos()
        self.assertNotIn('texto confidencial', str(exc.exception))
