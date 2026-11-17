"""Reúna periodicidade, prazo de inscrição e edição sem confundir suas datas."""
import re
from dataclasses import replace
from aplicacao.servicos.recuperacao.calendario.consulta import buscar_eventos
from aplicacao.servicos.recuperacao.calendario.edicoes import edicao_evento
from aplicacao.servicos.recuperacao.perguntas.evidencias import ficha_faq
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta


def consulta_inscricoes(pergunta):
    """Reconheça inscrições gerais, sem absorver dúvidas sobre taxas ou isenções.

    Args:
        pergunta (str): Consulta recebida.

    Returns:
        bool: Indica pergunta sobre o período de inscrição do vestibular.
    """
    texto = preparar_consulta(pergunta)
    return bool(re.search(r'vestibular', texto) and re.search(r'inscri|inscrev|candidat', texto)
                and not re.search(r'isenc|redu[cç]|taxa|pagamento|boleto|matricula', texto))


def consulta_sem_edicao(pergunta):
    """Verifique se a pergunta pede orientação geral, sem edição ou data explícita.

    Args:
        pergunta (str): Consulta normalizada.

    Returns:
        bool: Indica ausência de recorte por ano, semestre ou mês.
    """
    from aplicacao.servicos.extracao.calendario import MESES
    temporal = r'20\d{2}|semestre|primeiro|segundo|' + '|'.join(preparar_consulta(m) for m in MESES)
    return not re.search(temporal, preparar_consulta(pergunta))


def buscar_inscricoes(pergunta, textos, k):
    """Recupere os períodos publicados, identificando o ingresso de cada edição.

    Args:
        pergunta (str): Consulta pública.
        textos (list): Snapshot de documentos vigentes.
        k (int): Limite de evidências.

    Returns:
        list | None: FAQ e fatos compatíveis, vazio para edição ausente, ou None para outro assunto.
    """
    if not consulta_inscricoes(pergunta):
        return None
    eventos = sorted(buscar_eventos(pergunta, textos, k) or [], key=lambda t: edicao_evento(t.texto))
    eventos = periodo_recente(pergunta, eventos)
    gerais = [ficha_faq(t, {'periodicidade_vestibular'}, set()) for t in textos] if consulta_sem_edicao(pergunta) else []
    fontes = [t for t in gerais if t is not None] + [replace(t, tipo_info='inscricao') for t in eventos]
    return [replace(t, grupo_resposta='consulta:inscricoes') for t in fontes][:k]


def periodo_recente(pergunta, eventos):
    """Evite misturar edições antigas numa consulta sobre a situação atual publicada.

    Args:
        pergunta (str): Consulta que pode mencionar agora, hoje ou abertura.
        eventos (list): Prazos conhecidos; não representam consulta ao vivo à internet.

    Returns:
        list: Edição mais recente disponível, ou todas as edições solicitadas.
    """
    if not eventos or not re.search(r'\b(?:agora|hoje|atual|ainda|abertas?)\b', preparar_consulta(pergunta)):
        return eventos
    ultima = max(edicao_evento(t.texto) for t in eventos)
    return [t for t in eventos if edicao_evento(t.texto) == ultima]
