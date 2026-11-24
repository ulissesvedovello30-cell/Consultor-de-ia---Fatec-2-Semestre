"""Completude de grupos de fatos reconhecidos antes da apresentação."""


def completar_referencias(referencias, usados):
    """Mantenha juntos fatos de um mesmo pedido estruturado já reconhecido.

    Args:
        referencias (list): Índices do Gemini já validados quanto a tipo e limites.
        usados (list): Evidências efetivamente enviadas ao modelo.

    Returns:
        list: Índices únicos, incluindo os pares e cursos do mesmo grupo documental.

    Raises:
        ValueError: Quando a resposta completa exceder o limite de evidências.
    """
    grupos = {usados[i - 1].grupo_resposta for i in referencias if usados[i - 1].grupo_resposta}
    complementos = [i for i, t in enumerate(usados, 1) if t.grupo_resposta and t.grupo_resposta in grupos]
    unicos = list(dict.fromkeys(referencias))
    completos = sorted(set(unicos) | set(complementos))
    if len(completos) > 5:
        extras = [i for i in complementos if i not in unicos]
        completos = sorted(unicos + extras[:max(0, 5 - len(unicos))])
    return completos
