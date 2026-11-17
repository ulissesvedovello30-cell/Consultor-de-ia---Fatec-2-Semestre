"""Fusão de posições das buscas literal e linguística, sem misturar escalas."""
from collections import defaultdict
from dataclasses import replace
from aplicacao.servicos.recuperacao.classificacao_textual import chave_classificacao


def identidade(trecho):
    """Identifique a mesma evidência nas duas listas de recuperação.

    Args:
        trecho: Evidência com arquivo, página, versão e texto.

    Returns:
        tuple: Chave estável dentro do snapshot ativo.
    """
    return trecho.arquivo, trecho.pagina, trecho.versao_id, trecho.texto


def combinar(listas, palavras, limite):
    """Una listas com Reciprocal Rank Fusion e preserve a cobertura mínima.

    Args:
        listas (tuple): Resultados literais e resultados linguísticos.
        palavras (set): Assuntos normalizados da pergunta.
        limite (int): Máximo de trechos devolvidos.

    Returns:
        list: Evidências únicas, ordenadas por relevância e posições combinadas.
    """
    registros, posicoes = {}, defaultdict(float)
    for lista in listas:
        acumular(lista, registros, posicoes)
    chave = lambda t: (*chave_classificacao(t, palavras), posicoes[identidade(t)])
    return sorted(registros.values(), key=chave, reverse=True)[:limite]


def acumular(lista, registros, posicoes):
    """Some posições com constante sessenta e guarde a maior cobertura observada.

    Args:
        lista (list): Uma lista classificada de evidências.
        registros (dict): Evidências únicas acumuladas.
        posicoes (dict): Pontuações RRF por identidade.
    """
    for numero, trecho in enumerate(lista, 1):
        chave = identidade(trecho)
        anterior = registros.get(chave, trecho)
        registros[chave] = replace(trecho, similaridade=max(anterior.similaridade, trecho.similaridade))
        posicoes[chave] += 1 / (60 + numero)
