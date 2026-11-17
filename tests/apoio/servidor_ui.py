"""Servidor de testes de interface, isolado e restrito à máquina local."""
import tempfile
import os
from pathlib import Path
import uvicorn
from tests.apoio.servidor_web_teste import fabrica
from aplicacao.web.aplicacao import criar_app
from aplicacao.web.configuracao import ConfigWeb
from aplicacao.web.administracao.senhas import gerar_hash

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='consultor-ui-') as pasta:
        porta = int(os.getenv('TESTE_PORTA', '8767'))
        config = ConfigWeb(origem=f'http://127.0.0.1:{porta}', senha_hash=gerar_hash('senha-teste-interface-123'),
                           usuario='secretaria.teste@gmail.com',
                           seguranca_db=str(Path(pasta) / 'seguranca.db'),
                           totp_segredo=os.getenv('TESTE_TOTP', ''))
        uvicorn.run(criar_app(fabrica, config, 'teste'), host='127.0.0.1', port=porta, access_log=False)
