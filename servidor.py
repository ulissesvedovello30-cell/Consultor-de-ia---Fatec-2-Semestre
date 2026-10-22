"""Servidor integrado, executável no terminal comum ou no VS Code."""
import argparse
import logging
import threading
import time
import webbrowser
from seguranca.servidor import opcoes_uvicorn
import httpx
import uvicorn
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb


def argumentos():
    """Leia opções da CLI e retorne modo e preferência de abertura do navegador."""
    parser = argparse.ArgumentParser(description='Consultor Fatec com frontend e API.')
    parser.add_argument('--demo', action='store_true', help='SQLite fictício, sem Gemini ou MySQL.')
    parser.add_argument('--abrir', action='store_true', help='Abra o navegador quando o servidor responder.')
    return parser.parse_args()


def abrir_navegador(origem):
    """Aguarde prontidão por até 30 segundos e abra a origem local no navegador."""
    for _ in range(30):
        try:
            resposta = httpx.get(origem + '/api/health', timeout=1, trust_env=False)
            resposta.raise_for_status()
            webbrowser.open(origem)
            return
        except httpx.HTTPError:
            time.sleep(1)


def aplicativo(args):
    """Retorne aplicação e configuração para o modo explicitamente escolhido."""
    from debug_web import abrir_demo
    config = ConfigWeb.ambiente()
    fabrica = abrir_demo if args.demo else None
    return criar_app(fabrica, config, 'debug' if args.demo else 'oficial'), config


def main():
    """Inicie um único worker, sem logs de URL ou corpos de requisição."""
    args = argumentos()
    app, config = aplicativo(args)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    if args.abrir:
        threading.Thread(target=abrir_navegador, args=(config.origem,), daemon=True).start()
    print(f'Acesse {config.origem} — Ctrl+C encerra o servidor.')
    uvicorn.run(app, **opcoes_uvicorn(config.origem))


if __name__ == '__main__':
    main()
