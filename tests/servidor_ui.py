"""Servidor de testes de interface, isolado e restrito à máquina local."""
import tempfile
import os
from pathlib import Path
import uvicorn
from debug_web import abrir_demo
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='consultor-ui-') as pasta:
        config = ConfigWeb(origem='http://127.0.0.1:8767', senha_hash=gerar_hash('senha-teste-interface-123'),
                           seguranca_db=str(Path(pasta) / 'seguranca.db'),
                           totp_segredo=os.getenv('TESTE_TOTP', ''))
        uvicorn.run(criar_app(abrir_demo, config, 'debug'), host='127.0.0.1', port=8767, access_log=False)
