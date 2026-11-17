"""Identificação dos cursos a partir do corpo dos PPCs, sem usar o sumário."""
import re
from dataclasses import replace
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar

CATALOGO = re.compile(r'quais.*(?:cursos|graduacoes|tecnologos)|(?:cursos|graduacoes).*(?:oferec|exist|disponiv|tem)')
IDENTIFICACAO = re.compile(r'(?m)^3\.1\s+Identificação\s*\n(.*?)(?=\n3\.2\b|$)', re.S)


def buscar_cursos(pergunta, textos, k):
    """Recupere a identificação de cada curso sem confundir índice e conteúdo.

    Args:
        pergunta (str): Pergunta normalizada.
        textos (list): Trechos ativos do acervo.
        k (int): Máximo de evidências.

    Returns:
        list | None: Identificações documentadas ou None para a busca geral.
    """
    if not CATALOGO.search(normalizar(pergunta)):
        return None
    candidatos = [recortar(t) for t in textos if t.curso]
    por_curso = {t.curso: t for t in candidatos if t is not None}
    return [replace(por_curso[c], tipo_info='catalogo', grupo_resposta='consulta:catalogo') for c in sorted(por_curso)][:k]


def recortar(trecho):
    """Retorne somente a passagem original da seção de identificação.

    Args:
        trecho: Candidato com metadados e texto original do PPC.

    Returns:
        TrechoDocumento | None: Evidência curta, com identidade e página preservadas.
    """
    achado = IDENTIFICACAO.search(trecho.texto)
    if achado is None or re.search(r'\.{5,}', achado[1]):
        return None
    nome = re.search(r'O CST em (.*?)\s+é\s+Experimental', achado[1], re.S)
    return replace(trecho, texto=nome[1].strip(), similaridade=1.0) if nome else None
