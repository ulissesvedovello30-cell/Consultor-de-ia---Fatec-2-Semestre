"""Indexe documentos públicos pela CLI sem carregar um gerador local."""
import argparse
import time
from pathlib import Path
import config
from infra.gemini_http import ClienteGemini, ErroGemini
from dominio.erros import ErroBancoDeDados, ErroIndexacao
from montagem import banco_aberto, criar_base
from servicos.prazo import FIM


def argumentos():
    """Retorne caminhos e opção de substituição definidos na linha de comando."""
    parser = argparse.ArgumentParser(description='Indexa arquivos públicos revisados no MySQL.')
    parser.add_argument('arquivos', nargs='+', type=Path)
    parser.add_argument('--forcar', action='store_true')
    return parser.parse_args()


def indexar_um(base, caminho, forcar):
    """Valide arquivo, indexe em até cinco minutos e retorne número de trechos."""
    from web.uploads import validar_conteudo, validar_nome
    token = FIM.set(time.monotonic() + 300)
    try:
        validar_nome(caminho.name)
        validar_conteudo(caminho)
        return base.indexar_arquivo(caminho, forcar=forcar)
    finally:
        FIM.reset(token)


def main():
    """Abra banco e API, processe arquivos e sempre feche conexões."""
    args = argumentos()
    cliente = ClienteGemini(config.GEMINI_API_KEY)
    try:
        with banco_aberto() as engine:
            base = criar_base(engine, cliente)
            for caminho in args.arquivos:
                print(f'{caminho.name}: {indexar_um(base, caminho, args.forcar)} trechos publicados.')
    finally:
        cliente.fechar()


if __name__ == '__main__':
    try:
        main()
    except (ErroBancoDeDados, ErroIndexacao, ErroGemini, ValueError, TimeoutError) as erro:
        print(f'Falha: {erro}')
        raise SystemExit(1) from None
