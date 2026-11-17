"""Espera limitada para cotas do provedor durante a indexação."""
import logging
import re
import time
from time import sleep
from email.utils import parsedate_to_datetime
from math import isfinite
from servicos.prazo import FIM


def detalhes(resposta):
    """Leia somente os detalhes estruturados do erro HTTP, sem registrar seu conteúdo."""
    try:
        itens = resposta.json()['error']['details']
        return [item for item in itens if isinstance(item, dict)] if isinstance(itens, list) else []
    except (ValueError, TypeError, KeyError):
        return []


def violacoes(resposta):
    """Retorne as regras de cota informadas na resposta.

    Args:
        resposta: Resposta HTTP do Google.

    Returns:
        list[dict]: Regras estruturadas, sem a mensagem bruta do provedor.
    """
    return [regra for item in detalhes(resposta)
            for regra in (item['violations'] if isinstance(item.get('violations'), list) else [])
            if isinstance(regra, dict)]


def limite_zero(resposta):
    """Identifique limite zero estruturado ou no texto padronizado de cota.

    Args:
        resposta: Resposta HTTP do Google.

    Returns:
        bool: Verdadeiro somente quando o provedor informa limite zero.
    """
    if any(str(item.get('quotaValue')) == '0' for item in violacoes(resposta)):
        return True
    try:
        texto = resposta.json()['error']['message']
        return bool(re.search(r'(?i)\blimit:\s*0(?:[.,;]\s|\s|$)', texto))
    except (ValueError, KeyError, TypeError):
        return False


def resumo_cotas(resposta):
    """Formate somente identificadores e valores de limites conhecidos.

    Args:
        resposta: Resposta HTTP do Google.

    Returns:
        str: Diagnóstico sem chaves de API, perguntas ou conteúdo de documentos.
    """
    itens = [formatar_regra(regra) for regra in violacoes(resposta)[:4]]
    return ' '.join(filter(None, itens)) or 'O Google não identificou a regra de cota nesta resposta.'


def formatar_regra(regra):
    """Aceite apenas identificador de regra e limite numérico estruturados.

    Args:
        regra (dict): Violação de cota devolvida pelo Google.

    Returns:
        str: Identificador e valor, quando válidos.
    """
    nome = regra.get('quotaId', '')
    valor = str(regra.get('quotaValue', ''))
    if not isinstance(nome, str) or not re.fullmatch(r'(?:Embed|Generate|Requests|Tokens)[A-Za-z0-9_-]{0,160}', nome):
        return ''
    sufixo = f', limite={valor}' if re.fullmatch(r'[0-9]{1,12}', valor) else ''
    return f'Cota={nome}{sufixo}.'


def cota_longa(resposta):
    """Reconheça cotas explicitamente zeradas ou diárias na resposta do Google."""
    if limite_zero(resposta):
        return True
    return any('perday' in str(regra.get('quotaId', '')).lower()
               or 'daily' in str(regra.get('quotaId', '')).lower() for regra in violacoes(resposta))


def prazo_http(valor):
    """Interprete Retry-After em segundos ou data HTTP."""
    if valor.isascii() and valor.isdecimal() and len(valor) < 12:
        return float(valor)
    try:
        return max(0, parsedate_to_datetime(valor).timestamp() - time.time())
    except (ValueError, TypeError, OverflowError, AttributeError):
        return 0


def espera_sugerida(resposta):
    """Combine Retry-After e RetryInfo, respeitando o maior prazo."""
    espera = prazo_http(resposta.headers.get('retry-after', ''))
    for item in detalhes(resposta):
        duracao = str(item.get('retryDelay', ''))
        if re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,9})?s', duracao):
            espera = max(espera, float(duracao[:-1]))
    return espera


def descrever_cota(resposta):
    """Descreva o limite sem expor a chave ou a mensagem bruta do provedor."""
    if cota_longa(resposta):
        return 'Cota diária atingida ou limite zero; confira o modelo no Google AI Studio. ' + resumo_cotas(resposta)
    espera = espera_sugerida(resposta)
    dica = f' O Google indicou espera de {espera:.0f}s.' if espera else ''
    return 'Limite do projeto atingido; confira uso e cotas no Google AI Studio.' + dica + ' ' + resumo_cotas(resposta)


def tentar_novamente(resposta, tentativa):
    """Espere somente por um 429 transitório, dentro do prazo e do limite local."""
    if resposta.status_code != 429 or tentativa >= 6 or cota_longa(resposta):
        return False
    espera = max(min(120, 5 * 2**tentativa), espera_sugerida(resposta))
    fim = FIM.get()
    if not isfinite(espera) or espera > 120 or (fim is not None and time.monotonic() + espera >= fim):
        return False
    logging.getLogger(__name__).warning(
        'Cota Gemini (429): aguardando %.1fs; repetição %s/6. %s',
        espera, tentativa + 1, resumo_cotas(resposta))
    sleep(espera)
    return True
