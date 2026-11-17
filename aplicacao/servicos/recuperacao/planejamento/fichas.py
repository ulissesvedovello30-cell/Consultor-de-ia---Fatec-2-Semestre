"""Recupere propriedades dos PPCs separadamente para cada curso pedido."""
import re
from dataclasses import replace
from aplicacao.servicos.recuperacao.planejamento.consulta import assunto_curso
from aplicacao.servicos.recuperacao.filtros_acervo import mencionados, normalizar

CAMPOS = {
    'duracao': re.compile(r'Prazo de\s+integraliza[çc][aã]o.*?M[ií]nimo de.*?M[aá]ximo de.*?(?=\n\n-\s+|$)', re.S | re.I),
    'modalidade': re.compile(r'(?m)^-?\s*Modalidade[^\n]+', re.I),
}


def buscar_fichas(pergunta, textos, k):
    """Divida a consulta por propriedade e curso antes de recuperar os trechos.

    Args:
        pergunta (str): Consulta completa do visitante.
        textos (list): Snapshot de evidências vigentes.
        k (int): Máximo de resultados.

    Returns:
        list | None: Fichas correspondentes ou None para a busca geral.
    """
    assunto = assunto_curso(pergunta)
    if assunto not in CAMPOS:
        return None
    cursos = mencionados(pergunta, {t.curso for t in textos if t.curso})
    if not cursos and re.search(r'\bcurso (?:de|em) \w+', normalizar(pergunta)):
        return None
    elegiveis = [t for t in textos if t.curso and (not cursos or t.curso in cursos)]
    fichas = [recortar_ficha(t, assunto) for t in elegiveis]
    return unicas([t for t in fichas if t is not None])[:k] or None


def recortar_ficha(trecho, assunto):
    """Recorte somente um campo reconhecido, preservando números e origem.

    Args:
        trecho: Evidência original de um curso.
        assunto (str): Propriedade já identificada na pergunta.

    Returns:
        TrechoDocumento | None: Campo estruturado ou ausência desse campo.
    """
    achado = CAMPOS[assunto].search(trecho.texto)
    if achado is None:
        return None
    return replace(trecho, texto=achado[0].strip(), similaridade=1.0,
                   tipo_info=assunto, grupo_resposta='ficha:' + assunto)


def unicas(trechos):
    """Descarte cópias do mesmo campo sem juntar cursos ou ocultar divergências.

    Args:
        trechos (list): Campos encontrados nas fontes ativas.

    Returns:
        list: Campos únicos ordenados por curso e localização documental.
    """
    vistas, resultado = set(), []
    for trecho in sorted(trechos, key=lambda t: (t.curso, t.arquivo, t.pagina or 0)):
        chave = trecho.curso, ' '.join(trecho.texto.split())
        if chave not in vistas:
            resultado.append(trecho)
            vistas.add(chave)
    return resultado
