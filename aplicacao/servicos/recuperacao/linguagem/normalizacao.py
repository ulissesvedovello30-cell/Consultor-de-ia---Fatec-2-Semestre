"""Radicais portugueses e tolerância limitada a erros de digitação."""
from functools import lru_cache
from threading import local
from difflib import get_close_matches
import snowballstemmer
from aplicacao.servicos.recuperacao.consulta_textual import termos

_LOCAL = local()


@lru_cache(maxsize=20000)
def radical(palavra):
    """Normalize flexões com Snowball sem baixar modelos ou enviar dados externos.

    Args:
        palavra (str): Palavra normalizada da consulta ou do documento.

    Returns:
        str: Radical calculado pelo algoritmo português.
    """
    try:
        algoritmo = _LOCAL.algoritmo
    except AttributeError:
        algoritmo = _LOCAL.algoritmo = snowballstemmer.stemmer('portuguese')
    return algoritmo.stemWord(palavra)


def radicais(texto):
    """Produza os mesmos radicais para documentos e perguntas.

    Args:
        texto (str): Texto original ou consulta pública.

    Returns:
        set: Radicais das palavras de conteúdo.
    """
    return {radical(p) for p in termos(texto)}


def aproximar(palavra, vocabulario):
    """Aceite somente uma aproximação forte e sem empate próximo.

    Args:
        palavra (str): Radical ausente do índice.
        vocabulario (tuple): Vocabulário derivado dos documentos ativos.

    Returns:
        str: Radical aproximado ou a palavra original quando não houver segurança.
    """
    if not 5 <= len(palavra) <= 24 or palavra.isdecimal():
        return palavra
    candidatas = get_close_matches(palavra, vocabulario, n=2, cutoff=0.9)
    return candidatas[0] if len(candidatas) == 1 else palavra
