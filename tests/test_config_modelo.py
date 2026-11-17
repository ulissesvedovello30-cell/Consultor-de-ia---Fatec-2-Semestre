"""Regressão da configuração local dos modelos Gemini, sem acesso à rede."""
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from infra.gemini_http import ClienteGemini, nome_modelo

RAIZ = Path(__file__).resolve().parents[1]


def carregar(pasta, texto):
    """Leia a configuração ao lado de um .env isolado para o teste."""
    modulo = pasta / 'config.py'
    modulo.write_bytes((RAIZ / 'config.py').read_bytes())
    (pasta / '.env').write_text(texto, encoding='utf-8')
    with patch.dict(os.environ, {}, clear=True):
        return runpy.run_path(str(modulo))


class ConfiguracaoModelo(unittest.TestCase):
    def test_env_antigo_e_novo(self):
        exemplo = (RAIZ / '.env.example').read_text()
        with tempfile.TemporaryDirectory() as tmp:
            for texto in (exemplo, '', 'GEMINI_MODELO=', 'GEMINI_MODELO="  "'):
                cfg = carregar(Path(tmp), texto + '\nGEMINI_API_KEY=teste\n')
                cfg['validar_gemini']()
                self.assertEqual(cfg['MODELO_GERADOR'], 'gemini-3.5-flash')

    def test_key_ainda_obrigatoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = carregar(Path(tmp), 'GEMINI_MODELO=\n')
            with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
                cfg['validar_gemini']()

    def test_invalido_identifica_campo(self):
        with tempfile.TemporaryDirectory() as tmp:
            for campo in ('GEMINI_MODELO', 'GEMINI_EMBEDDING'):
                cfg = carregar(Path(tmp), f'BUSCA_ACERVO=gemini\n{campo}=models/../errado\nGEMINI_API_KEY=teste')
                with self.assertRaisesRegex(ValueError, campo):
                    cfg['validar_gemini']()

    def test_recurso_usa_id_explicito(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = carregar(Path(tmp), 'GEMINI_MODELO=" models/outro-modelo "\nGEMINI_API_KEY=teste')
            cfg['validar_gemini']()
            modelo = cfg['MODELO_GERADOR']
        pedidos = []
        def resposta(request):
            pedidos.append(request.url.path)
            return httpx.Response(200, json={})
        cliente = ClienteGemini('teste', httpx.MockTransport(resposta))
        try:
            cliente.chamar(modelo, 'generateContent', {})
        finally:
            cliente.fechar()
        self.assertEqual(nome_modelo(modelo), 'outro-modelo')
        self.assertEqual(pedidos, ['/v1beta/models/outro-modelo:generateContent'])
