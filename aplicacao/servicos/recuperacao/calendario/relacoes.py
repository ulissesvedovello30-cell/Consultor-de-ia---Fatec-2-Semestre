"""Associe o recesso à próxima volta às aulas na mesma versão do calendário."""
import hashlib
import re
from datetime import date
from dataclasses import replace
from aplicacao.servicos.extracao.calendario import MESES
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar

MESES_NUMEROS = {normalizar(m): i for i, m in enumerate(MESES, 1)}
DATA = re.compile(r'(\d{1,2}) de (' + '|'.join(MESES_NUMEROS) + r') de (20\d{2})')


def data_final(texto):
    """Leia a última data completa no cabeçalho de um fato normalizado.

    Args:
        texto (str): Fato datado produzido pelo extrator do calendário.

    Returns:
        date | None: Data explícita ou ausência quando não houver data completa.
    """
    encontrados = DATA.findall(normalizar(texto.partition(':')[0]))
    try:
        dia, mes, ano = encontrados[-1]
        return date(int(ano), MESES_NUMEROS[mes], int(dia))
    except (IndexError, KeyError, ValueError):
        return None


def mesmo_calendario(a, b):
    """Exija a mesma fonte e versão antes de relacionar dois eventos.

    Args:
        a: Primeiro evento.
        b: Segundo evento.

    Returns:
        bool: Indica que as evidências pertencem ao mesmo calendário.
    """
    return (a.arquivo, a.versao_id) == (b.arquivo, b.versao_id)


def volta_seguinte(recesso, textos):
    """Localize o início das aulas próximo ao fim do recesso, sem usar início do semestre.

    Args:
        recesso: Evento com intervalo oficial de recesso.
        textos (list): Todos os fatos vigentes do acervo.

    Returns:
        TrechoDocumento | None: Próximo início de aulas documentalmente publicado.
    """
    fim = data_final(recesso.texto)
    candidatos = [(data_final(t.texto), t) for t in textos if mesmo_calendario(recesso, t)
                  and re.search(r'inicio das aulas', normalizar(t.texto))]
    proximos = [(d, t) for d, t in candidatos if d is not None and fim is not None and 0 < (d - fim).days <= 45]
    return min(proximos, key=lambda item: item[0])[1] if proximos else None


def grupo_recesso(trecho):
    """Identifique o par de eventos sem guardar perguntas ou misturar calendários.

    Args:
        trecho: Recesso usado como origem da relação.

    Returns:
        str: Identidade do grupo de evidências relacionadas.
    """
    origem = repr((trecho.arquivo, trecho.versao_id, trecho.texto)).encode()
    return 'recesso:' + hashlib.sha256(origem).hexdigest()


def parear(recesso, textos):
    """Preserve o recesso oficial e acrescente o retorno quando houver evidência.

    Args:
        recesso: Evento oficial selecionado pela consulta.
        textos (list): Snapshot completo dos documentos vigentes.

    Returns:
        list: Recesso e, quando publicado, início das aulas relacionado.
    """
    grupo = grupo_recesso(recesso)
    retorno = volta_seguinte(recesso, textos)
    oficial = replace(recesso, tipo_info='recesso', grupo_resposta=grupo)
    if retorno is None:
        return [oficial]
    return [oficial, replace(retorno, similaridade=1.0, tipo_info='retorno_aulas', grupo_resposta=grupo)]


def completar_recessos(pergunta, selecionados, textos, limite):
    """Recupere fatos complementares para perguntas sobre férias ou recesso.

    Args:
        pergunta (str): Consulta normalizada.
        selecionados (list): Eventos aprovados pelo assunto e pelo período.
        textos (list): Snapshot completo do mesmo acervo.
        limite (int): Máximo de evidências permitido pela recuperação.

    Returns:
        list: Fatos associados, sem inventar intervalos de férias.
    """
    if not re.search(r'ferias|recesso|receso|descanso', pergunta):
        return selecionados
    pares = [t for recesso in selecionados for t in parear(recesso, textos)]
    return pares[:limite]
