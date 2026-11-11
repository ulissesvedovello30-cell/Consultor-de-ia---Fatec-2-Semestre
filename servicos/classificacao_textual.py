"""Ordenação de evidências textuais sem alterar o conteúdo dos documentos."""
import re
from servicos.consulta_textual import cobertura

TITULO = re.compile(r'(?m)^\s*(?:[0-9]+\.)+[0-9]*\s+([^\n]{3,120})$')
PONTILHADO = re.compile(r'\.{5,}|…{3,}')


def chave_classificacao(trecho, palavras):
    """Prefira conteúdo com título pertinente a entradas de sumário.

    Args:
        trecho: Evidência com pontuação de cobertura já calculada.
        palavras (set[str]): Assuntos relevantes da pergunta.

    Returns:
        tuple: Cobertura, presença de conteúdo e afinidade do título; empates mantêm BM25.
    """
    corpo = not bool(PONTILHADO.search(trecho.texto))
    titulos = TITULO.findall(trecho.texto)
    afinidade = max((cobertura(palavras, titulo) for titulo in titulos), default=0.0)
    return trecho.similaridade, corpo, afinidade
