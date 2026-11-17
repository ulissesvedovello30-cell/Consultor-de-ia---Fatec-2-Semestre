"""Identificação da edição e precedência explícita de atualizações do vestibular."""
import re
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar


def edicao_evento(texto):
    """Leia o semestre de ingresso na descrição, separado da data do evento.

    Args:
        texto (str): Evento datado, com dois-pontos antes da descrição.

    Returns:
        tuple[str, str]: Ano e semestre publicados, ou campos vazios.
    """
    achado = re.search(r'([12])[ºo°]?\s+semestre de (20\d{2})', normalizar(texto.partition(':')[2]))
    return (achado[2], achado[1]) if achado else ('', '')


def etapa_evento(texto):
    """Diferencie inscrição, pagamento e exame antes de comparar atualizações.

    Args:
        texto (str): Descrição de um fato datado.

    Returns:
        str: Etapa reconhecida, ou vazio para outros eventos.
    """
    descricao = normalizar(texto.partition(':')[2])
    if re.search(r'^pagamento', descricao):
        return 'pagamento'
    if re.search(r'^inscrico|^previsao do periodo de inscrico', descricao):
        return 'inscricao'
    return 'exame' if re.search(r'^exame|^previsao da realizacao do exame', descricao) else ''


def priorizar_atualizacoes(eventos):
    """Retire uma previsão quando existe atualização explícita da mesma etapa e edição.

    Args:
        eventos (list): Fatos elegíveis, já limitados ao assunto da consulta.

    Returns:
        list: Atualizações e fatos sem substituto; divergências confirmadas permanecem visíveis.
    """
    atualizadas = {(edicao_evento(t.texto), etapa_evento(t.texto)) for t in eventos
                   if re.search(r'prazo prorrogado|horario confirmado', normalizar(t.texto))}
    return [t for t in eventos if 'previsao' not in normalizar(t.texto) or
            (edicao_evento(t.texto), etapa_evento(t.texto)) not in atualizadas]
