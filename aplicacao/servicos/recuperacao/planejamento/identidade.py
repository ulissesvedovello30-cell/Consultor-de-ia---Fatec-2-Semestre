"""Nomes de cursos derivados dos PPCs, sem alterar o esquema do SQLite."""
from dataclasses import replace
from aplicacao.servicos.recuperacao.cursos import recortar


def nomes_cursos(textos):
    """Leia os nomes completos no corpo dos PPCs vigentes.

    Args:
        textos (list): Snapshot já validado do acervo.

    Returns:
        dict: Sigla de curso e nome explicitamente encontrado no documento.
    """
    identificacoes = [recortar(t) for t in textos if t.curso]
    return {t.curso: t.texto for t in identificacoes if t is not None}


def identificar_resultados(resultados, textos):
    """Associe o nome do curso a cada evidência antes de montar o contexto.

    Args:
        resultados (list): Trechos recuperados para a consulta.
        textos (list): Evidências usadas para identificar os cursos.

    Returns:
        list: Cópias com nomes completos, sem gravar metadados novos no banco.
    """
    nomes = nomes_cursos(textos)
    return [replace(t, nome_curso=nomes.get(t.curso, t.curso)) for t in resultados]
