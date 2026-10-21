import argparse
import logging
import sys
from pathlib import Path

import config
from dominio.erros import ErroBancoDeDados, ErroIndexacao
from infra.banco_de_dados import criar_engine
from infra.repositorio_trechos import RepositorioTrechos
from montagem import configurar_banco
from servicos.base_conhecimento import BaseConhecimento
from servicos.gerador_embeddings import GeradorEmbeddings


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    analisador = argparse.ArgumentParser(description="Indexa documentos (.pdf, .docx, .txt) na base de conhecimento do RAG.")
    analisador.add_argument(
        "arquivos",
        nargs="+",
        type=Path,
        help="um ou mais arquivos .pdf, .docx ou .txt (em lista de fatos, comece cada fato com '- ')",
    )
    analisador.add_argument("--forcar", action="store_true", help="reindexa mesmo que o arquivo já esteja no banco")
    analisador.add_argument(
        "--tamanho",
        type=int,
        default=450,
        help="máximo de caracteres por trecho (450 cabe no modelo de embeddings; use ~300 para datas e horários)",
    )
    argumentos = analisador.parse_args()

    engine = criar_engine(configurar_banco())
    falhas = 0
    try:
        base = BaseConhecimento(RepositorioTrechos(engine), GeradorEmbeddings(config.MODELO_EMBEDDING))
        for caminho in argumentos.arquivos:
            try:
                total = base.indexar_arquivo(caminho, forcar=argumentos.forcar, tamanho_trecho=argumentos.tamanho)
            except ErroIndexacao as e:
                print(f"ERRO: {e}")
                falhas += 1
            else:
                print(f"{caminho.name}: {total} trechos indexados" if total else f"{caminho.name}: já indexado")
    except ErroBancoDeDados as e:
        print(f"ERRO no banco: {e}")
        return 1
    finally:
        engine.dispose()

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
