"""Direcione consultas a fontes adequadas sem acrescentar fatos ao acervo."""
from aplicacao.servicos.recuperacao.calendario.consulta import buscar_eventos
from aplicacao.servicos.recuperacao.cursos import buscar_cursos
from aplicacao.servicos.recuperacao.planejamento.fichas import buscar_fichas
from aplicacao.servicos.recuperacao.perguntas.consulta import buscar_frequentes
from aplicacao.servicos.recuperacao.calendario.inscricoes import buscar_inscricoes


def buscar_contexto(pergunta, textos, k):
    """Priorize calendário ou catálogo quando a intenção estiver explícita.

    Args:
        pergunta (str): Consulta do visitante.
        textos (list): Evidências ativas e vigentes.
        k (int): Máximo de resultados.

    Returns:
        list | None: Resultados dirigidos, ou None para a recuperação linguística.
    """
    for recuperar in (buscar_frequentes, buscar_fichas, buscar_inscricoes, buscar_eventos, buscar_cursos):
        resultado = recuperar(pergunta, textos, k)
        if resultado is not None:
            return resultado
    return None
