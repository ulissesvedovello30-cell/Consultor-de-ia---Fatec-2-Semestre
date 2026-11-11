"""Publique os documentos institucionais no SQLite configurado."""
import argparse
import config
from dominio.erros import ErroBancoDeDados, ErroIndexacao
from infra.gemini_http import ClienteGemini, ErroGemini
from montagem import banco_aberto, criar_base
from servicos.inicializar_acervo import publicar_iniciais


def publicar(engine, cliente, forcar):
    """Atualize o acervo dentro de um prazo de indexação separado do chat.

    Args:
        engine: Engine de persistência configurado.
        cliente: Cliente Gemini autenticado.
        forcar (bool): Reindexação explícita.

    Returns:
        dict: Quantidade de trechos por arquivo.
    """
    return publicar_iniciais(engine, criar_base(engine, cliente), forcar)


def main():
    """Leia a opção de reindexação e encerre os recursos após a publicação."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forcar', action='store_true')
    args = parser.parse_args()
    cliente = ClienteGemini(config.GEMINI_API_KEY)
    try:
        with banco_aberto() as engine:
            print(publicar(engine, cliente, args.forcar))
    finally:
        cliente.fechar()


if __name__ == '__main__':
    try:
        main()
    except (ErroBancoDeDados, ErroIndexacao, ErroGemini, ValueError, TimeoutError, NotImplementedError):
        print('Não foi possível publicar. Confira banco, fontes, chave e cota; tente novamente.')
        raise SystemExit(1) from None
