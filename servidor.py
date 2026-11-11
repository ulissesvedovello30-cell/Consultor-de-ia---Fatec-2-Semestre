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
import config as configuracao
from dominio.erros import ErroBancoDeDados
from infra.tunel_ngrok import escolher_tunel


def argumentos():
    """Leia opções da CLI e retorne modo e preferência de abertura do navegador."""
    parser = argparse.ArgumentParser(description='Consultor Fatec com frontend e API.')
    parser.add_argument('--perfil', choices=('mvp', 'postgres'), default=configuracao.PERFIL,
                        help='mvp: Gemini + SQLite; postgres: reservado, ainda indisponível.')
    parser.add_argument('--ngrok', action='store_true', help='Abra túnel HTTPS opcional no modo oficial.')
    parser.add_argument('--abrir', action='store_true', help='Abra o navegador quando o servidor responder.')
    return parser.parse_args()


def abrir_navegador(origem):
    """Aguarde prontidão durante a preparação inicial e abra a origem local no navegador."""
    for _ in range(960):
        try:
            resposta = httpx.get(origem + '/api/health', timeout=1, trust_env=False)
            resposta.raise_for_status()
            webbrowser.open(origem)
            return
        except httpx.HTTPError:
            time.sleep(1)


def aplicativo(args, config=None):
    """Retorne aplicação e configuração para o modo explicitamente escolhido."""
    config = config or ConfigWeb.ambiente()
    return criar_app(configuracao=config, modo='mvp'), config


def executar(args, config):
    """Inicie o servidor com a mesma origem usada pelos cookies e pelo frontend.

    Args:
        args: Opções da linha de comando.
        config: Configuração local ou configuração HTTPS do túnel.
    """
    opcoes = opcoes_uvicorn(config.origem)
    app, config = aplicativo(args, config)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    if args.abrir:
        threading.Thread(target=abrir_navegador, args=(config.origem,), daemon=True).start()
    print(f'Acesse {config.origem} — Ctrl+C encerra o servidor.')
    uvicorn.run(app, **opcoes)


def main():
    """Selecione o túnel opcional e garanta sua limpeza ao encerrar."""
    args = argumentos()
    configuracao.PERFIL = args.perfil
    validar_perfil(args.perfil)
    configuracao.validar_gemini()
    with escolher_tunel(args.ngrok, ConfigWeb.ambiente()) as config:
        executar(args, config)


def validar_perfil(perfil):
    """Recuse o perfil futuro antes de abrir o servidor ou o túnel.

    Args:
        perfil (str): Perfil solicitado pelo terminal.

    Raises:
        NotImplementedError: Se o perfil ainda não estiver disponível.
    """
    from infra.banco_de_dados import postgres_pendente
    try:
        (True,).index(perfil == 'mvp')
    except ValueError:
        postgres_pendente(None)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, ErroBancoDeDados, NotImplementedError) as erro:
        print(str(erro))
        raise SystemExit(1) from None
