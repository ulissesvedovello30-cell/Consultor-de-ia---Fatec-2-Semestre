"""Configuração do servidor de aplicação e da fronteira de confiança do proxy."""
import os
from ipaddress import ip_address
from urllib.parse import urlsplit


def proxies_confiaveis(valor):
    """Aceite apenas IPs de loopback explícitos; nunca confie em cabeçalhos de todos."""
    enderecos = [parte.strip() for parte in valor.split(',') if parte.strip()]
    try:
        if any(not ip_address(ip).is_loopback for ip in enderecos):
            raise ValueError('Proxy externo.')
    except ValueError:
        raise ValueError('TRUSTED_PROXIES aceita somente IPs de loopback, sem * ou redes.') from None
    return ','.join(enderecos)


def opcoes_uvicorn(origem):
    """Retorne limites do Uvicorn; habilite IP encaminhado só por proxy local configurado."""
    confiaveis = proxies_confiaveis(os.getenv('TRUSTED_PROXIES', ''))
    url = urlsplit(origem)
    porta = int(os.getenv('APP_PORT', str(8000 if url.scheme == 'https' else url.port or 8000)))
    validar_porta(url, porta)
    return dict(host='127.0.0.1', port=porta, workers=1, access_log=False,
                proxy_headers=bool(confiaveis), forwarded_allow_ips=confiaveis,
                limit_concurrency=64, backlog=128, timeout_keep_alive=5,
                h11_max_incomplete_event_size=16384, server_header=False, date_header=False)


def validar_porta(url, porta):
    """Valide a porta interna e sua correspondência com a origem HTTP local.

    Args:
        url: Origem pública analisada por urlsplit.
        porta (int): Porta de escuta do servidor.

    Raises:
        ValueError: Se a porta for inválida ou divergir da origem local.
    """
    try:
        (True,).index(1 <= porta <= 65535)
        (True,).index(url.scheme == 'https' or porta == (url.port or 80))
    except ValueError:
        raise ValueError('Confira APP_PORT (1 a 65535); em HTTP ela deve coincidir com APP_ORIGIN.') from None
