"""Busque férias, provas do vestibular e eventos conforme sua descrição real."""
import re
from dataclasses import replace
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar
from aplicacao.servicos.recuperacao.consulta_textual import termos_consulta, cobertura, termos
from aplicacao.servicos.recuperacao.calendario.filtros import filtrar_eventos
from aplicacao.servicos.recuperacao.calendario.relacoes import completar_recessos
from aplicacao.servicos.recuperacao.calendario.edicoes import priorizar_atualizacoes

DATADO = re.compile(r'^- (?:Dia |Dias |De |Data a definir)')
CALENDARIO = re.compile(r'calendario|evento|feriado|ferias|recesso|receso|descanso|hackathon|aula magna|fatec integra|'
    r'(?:inscrev|pagamento|pagar|boleto).*vestibular|vestibular.*(?:inscrev|pagamento|pagar|boleto)|'
    r'inicio.*semestre|comec.*(?:aula|semestre)|inicia.*(?:aula|semestre)|'
    r'(?:quando|data|dia|prazo|periodo|inscri).*(?:matricula|inscric|vestibular|aula|semestre)')
CULTURA = re.compile(r'hackathon|aula magna|fatec integra|palestra|visita tecnica|semana d[ae]|'
    r'aniversario da fatec|setembro amarelo|outubro rosa|novembro azul|congresso|seminario|forum|workshop')


def buscar_eventos(pergunta, textos, k):
    """Selecione fatos datados quando a pergunta trata do calendário.

    Args:
        pergunta (str): Consulta recebida.
        textos (list): Trechos vigentes do acervo.
        k (int): Limite de evidências.

    Returns:
        list | None: Fatos compatíveis, vazio para recorte temporal ausente ou None para busca geral.
    """
    pergunta = normalizar(pergunta)
    if not CALENDARIO.search(pergunta):
        return None
    eventos = filtrar_eventos(pergunta, [t for t in textos if DATADO.match(t.texto)])
    selecionados = selecionar(pergunta, priorizar_atualizacoes(filtrar_assunto(pergunta, eventos)), k)
    if not selecionados and not recorte_exclusivo_calendario(pergunta):
        return None
    return completar_recessos(pergunta, selecionados, textos, k)


def recorte_exclusivo_calendario(pergunta):
    """Mantenha resposta vazia apenas quando a consulta restringe o calendário por data ou categoria fechada."""
    from aplicacao.servicos.extracao.calendario import MESES
    if re.search(r'\b20\d{2}\b|ferias|recesso|receso|descanso|feriado|vestibular', pergunta):
        return True
    if re.search(r'quais?.*(?:evento|calendario)|evento.*calendario', pergunta):
        return True
    return any(re.search(r'\b' + normalizar(m) + r'\b', pergunta) for m in MESES)


def filtrar_assunto(pergunta, eventos):
    """Separe exame, inscrição, recesso e feriado antes da classificação.

    Args:
        pergunta (str): Consulta normalizada.
        eventos (list): Fatos com recorte temporal aplicado.

    Returns:
        list: Eventos do assunto perguntado, sem usar matrículas como data de prova.
    """
    regras = [(r'ferias|recesso|receso|descanso', r'recesso|ferias'),
              (r'feriado', r'feriado|nao havera aula'),
              (r'vestibular', assunto_vestibular(pergunta))]
    for consulta, documento in regras:
        if re.search(consulta, pergunta):
            return [t for t in eventos if re.search(documento, normalizar(t.texto))]
    return eventos


def assunto_vestibular(pergunta):
    """Defina qual etapa do vestibular foi solicitada.

    Args:
        pergunta (str): Consulta normalizada.

    Returns:
        str: Expressão aplicada somente à descrição dos eventos.
    """
    if re.search(r'isen|redu[cç]', pergunta):
        return r'(?:isencao|reducao).*vestibular'
    if re.search(r'pagamento|pagar|boleto', pergunta):
        return r'^[^:]+:\s*pagamento.*taxa.*vestibular'
    if re.search(r'inscri|inscrev', pergunta):
        return r'^[^:]+:\s*(?:previsao do periodo de )?inscricoes para (?:o )?vestibular'
    if re.search(r'matricula|chamada|lista|resultado|classifica', pergunta):
        return r'vestibular'
    return r'(?:realizacao|exame|prova).*vestibular'


def selecionar(pergunta, eventos, k):
    """Classifique evidências sem exigir que férias apareça literalmente no PDF.

    Args:
        pergunta (str): Consulta normalizada.
        eventos (list): Eventos do assunto apropriado.
        k (int): Limite de resultados.

    Returns:
        list: Fatos classificados, preservando previsões e datas a definir.
    """
    if re.search(r'ferias|recesso|receso|descanso|(?:inscri|inscrev|pagamento|pagar|boleto).*vestibular|vestibular.*(?:inscri|inscrev|pagamento)', pergunta):
        return [replace(t, similaridade=1.0) for t in eventos][:k]
    if re.search(r'quais?.*(?:evento|calendario)|evento.*calendario', pergunta):
        return [replace(t, similaridade=1.0) for t in eventos if CULTURA.search(normalizar(t.texto))][:k]
    palavras = palavras_evento(pergunta)
    pontuados = [replace(t, similaridade=cobertura(palavras, t.texto)) for t in eventos]
    return [t for t in sorted(pontuados, key=lambda t: t.similaridade, reverse=True) if t.similaridade >= 0.6][:k]


def palavras_evento(pergunta):
    """Retire marcadores conversacionais e termos de ação já usados no filtro.

    Args:
        pergunta (str): Consulta normalizada.

    Returns:
        set: Palavras de conteúdo usadas para pontuar os eventos.
    """
    palavras = termos_consulta(pergunta) - {'calendario', 'evento'}
    palavras |= termos(pergunta) & {'aula'}
    if re.search(r'vestibular.*|ferias|recesso|receso|feriado', pergunta):
        palavras -= {'inicio', 'prova', 'aula', 'nao', 'terao'}
    return palavras
