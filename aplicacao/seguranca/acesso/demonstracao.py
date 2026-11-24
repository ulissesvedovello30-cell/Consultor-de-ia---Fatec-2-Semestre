"""Código fixo restrito ao acesso de demonstração local."""
import hmac
import re
from urllib.parse import urlsplit
from aplicacao.seguranca.http.contratos import CredenciaisInvalidas


def validar_demonstracao(config):
    """Exija origem local e um código explícito no modo de apresentação.

    Args:
        config: Configuração web já carregada pelo servidor.

    Raises:
        ValueError: Se a origem não for local ou faltar o código de seis dígitos.
    """
    if not config.demonstracao:
        return
    host = urlsplit(config.origem).hostname
    if host not in {'127.0.0.1', 'localhost', '::1', 'testserver'}:
        raise ValueError('O acesso de demonstração requer uma origem local. Desative ADMIN_DEMONSTRACAO para acesso público.')
    if not re.fullmatch(r'[0-9]{6}', config.codigo_demonstracao):
        raise ValueError('Configure ADMIN_CODIGO_DEMONSTRACAO com seis dígitos.')


def conferir_codigo(config, codigo):
    """Confira o código fixo sem consumir um passo temporal de TOTP.

    Args:
        config: Configuração que habilitou explicitamente a demonstração.
        codigo (str): Código informado no formulário.

    Raises:
        CredenciaisInvalidas: Se o código não corresponder ao configurado.
    """
    if not hmac.compare_digest(codigo.encode('utf-8'), config.codigo_demonstracao.encode('utf-8')):
        raise CredenciaisInvalidas('Credenciais inválidas.')
