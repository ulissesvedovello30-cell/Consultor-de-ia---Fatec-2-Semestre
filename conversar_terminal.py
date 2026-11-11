"""Conversa com o bot no terminal, sem site.

    python conversar_terminal.py                     # demonstração leve: sem banco, sem baixar modelos
    python conversar_terminal.py --modelos-reais     # MiniLM + IA local de verdade (baixa os modelos)
    python conversar_terminal.py --mysql             # tudo de verdade: MySQL do .env + modelos locais
    python conversar_terminal.py outro.pdf --pergunta "Quando é a prova?"

Sem argumentos, indexa dados/turma_exemplo.pdf. Digite `sair` para encerrar.
"""
import argparse
import asyncio
import logging
from pathlib import Path

import config
from core.chatbot import Chatbot
from infra.repositorio_em_memoria import RepositorioEmMemoria
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG

_PADRAO = Path(__file__).parent / "dados" / "turma_exemplo.pdf"


def montar_em_memoria(arquivos: list[Path], modelos_reais: bool, tamanho_trecho: int):
    if modelos_reais:
        from servicos.gerador_embeddings import GeradorEmbeddings
        from servicos.gerador_local import GeradorLocal

        embedder = GeradorEmbeddings(config.MODELO_EMBEDDING)
        gerador = GeradorLocal(config.MODELO_GERADOR, tempo_limite=config.RAG_TEMPO_GERACAO)
        print("Carregando modelos (a primeira vez baixa vários GB)...")
        embedder.carregar()
        gerador.carregar()
        limiar = config.RAG_LIMIAR_SIMILARIDADE
    else:
        from servicos.demo_offline import EmbeddingsLexicais, GeradorExtrativo

        embedder, gerador = EmbeddingsLexicais(), GeradorExtrativo()
        limiar = 0.2  # o embedding lexical tem outra escala de similaridade que o MiniLM

    base = BaseConhecimento(RepositorioEmMemoria(), embedder)
    for arquivo in arquivos:
        total = base.indexar_arquivo(arquivo, tamanho_trecho=tamanho_trecho)
        print(f"{arquivo.name}: {total} trechos indexados")
    return Chatbot(ConsultorRAG(base, gerador, limiar_similaridade=limiar)), base


def conversar(chatbot: Chatbot, base, argumentos) -> None:
    while True:
        texto = argumentos.pergunta or input("\nVocê: ").strip()
        if texto.lower() in {"sair", "exit", "quit"}:
            return
        if texto:
            resposta = asyncio.run(chatbot.processar_mensagem("terminal", texto))
            print(f"\nBot: {resposta.texto}")
            if argumentos.mostrar_trechos:
                for t in base.buscar(texto, 3):
                    print(f"  [{t.similaridade:.3f}] {t.rotulo}: {t.texto[:90]}")
        if argumentos.pergunta:
            return


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    analisador = argparse.ArgumentParser(description="Conversa com o bot no terminal.")
    analisador.add_argument("arquivos", nargs="*", type=Path, help="documentos .pdf, .docx ou .txt (modos sem --mysql)")
    analisador.add_argument("--modelos-reais", action="store_true", help="usa MiniLM e a IA local (baixa os modelos)")
    analisador.add_argument("--mysql", action="store_true", help="usa o MySQL do .env e os documentos já indexados nele")
    analisador.add_argument("--tamanho", type=int, default=300, help="máximo de caracteres por trecho")
    analisador.add_argument("--pergunta", help="faz uma pergunta e encerra")
    analisador.add_argument("--mostrar-trechos", action="store_true", help="mostra os trechos achados e a similaridade")
    argumentos = analisador.parse_args()

    if argumentos.mysql:
        from montagem import abrir_chatbot

        with abrir_chatbot() as (chatbot, base):
            conversar(chatbot, base, argumentos)
        return

    chatbot, base = montar_em_memoria(argumentos.arquivos or [_PADRAO], argumentos.modelos_reais, argumentos.tamanho)
    if not argumentos.modelos_reais:
        print("\nModo demonstração leve: as respostas apenas repetem os trechos achados.")
    conversar(chatbot, base, argumentos)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print()
