"""Transporte ASGI para testar a interface sem abrir uma porta TCP."""
import base64
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from tests.apoio.servidor_web_teste import fabrica
from aplicacao.web.aplicacao import criar_app
from aplicacao.web.configuracao import ConfigWeb
from aplicacao.web.administracao.senhas import gerar_hash


def atender(cliente, pedido):
    """Traduza uma requisição da interface para o cliente ASGI de testes.

    Args:
        cliente: Cliente persistente da aplicação de teste.
        pedido (dict): Método, caminho, cabeçalhos e corpo codificado.

    Returns:
        dict: Status, cabeçalhos e corpo, sem conexão de rede.
    """
    corpo = base64.b64decode(pedido.get('corpo', ''))
    resposta = cliente.request(pedido['metodo'], pedido['url'], headers=pedido['cabecalhos'], content=corpo)
    return dict(status=resposta.status_code, cabecalhos=dict(resposta.headers), texto=resposta.text)


def executar_pedidos(cliente):
    """Mantenha a sessão enquanto o processo Node executar os testes.

    Args:
        cliente: Cliente ASGI mantido aberto durante a leitura da entrada.
    """
    print(json.dumps({'pronta': True}), flush=True)
    for linha in sys.stdin:
        try:
            resultado = atender(cliente, json.loads(linha))
        except (ValueError, KeyError, TypeError):
            resultado = {'erro': 'Requisição de teste inválida.'}
        print(json.dumps(resultado, ensure_ascii=False), flush=True)


def iniciar_ponte(pasta):
    """Componha a aplicação isolada usada pelo teste DOM.

    Args:
        pasta (str): Diretório temporário exclusivo da execução.
    """
    origem = os.getenv('TESTE_ORIGEM', 'http://127.0.0.1:8767')
    config = ConfigWeb(origem=origem, usuario='secretaria.teste@gmail.com',
        senha_hash=gerar_hash('senha-teste-interface-123'), totp_segredo=os.getenv('TESTE_TOTP', ''),
        seguranca_db=str(Path(pasta) / 'seguranca.db'))
    with TestClient(criar_app(fabrica, config, 'teste'), base_url=origem) as cliente:
        executar_pedidos(cliente)


if __name__ == '__main__':
    with TemporaryDirectory(prefix='consultor-ponte-') as pasta:
        iniciar_ponte(pasta)
