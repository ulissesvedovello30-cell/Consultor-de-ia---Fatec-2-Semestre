"""Identificador local do administrador, independente de login Google."""
import re


def normalizar_usuario(usuario):
    """Normalize o identificador sem aceitar espaços internos ou controles.

    Args:
        usuario (str): Nome ou e-mail informado para login local.

    Returns:
        str: Identificador sem espaços externos e em minúsculas.

    Raises:
        ValueError: Se o identificador não tiver um formato válido.
    """
    valor = usuario.strip().casefold()
    try:
        (True,).index(0 < len(valor) <= 100 and not any(c.isspace() or ord(c) < 32 for c in valor))
    except ValueError:
        raise ValueError('Identificador inválido. Use até 100 caracteres sem espaços.') from None
    return valor


def validar_email(email):
    """Confira o formato do e-mail escolhido para a conta administrativa.

    Args:
        email (str): Endereço digitado no configurador local.

    Returns:
        str: Endereço normalizado; não comprova a posse da caixa postal.

    Raises:
        ValueError: Se o endereço não tiver formato de e-mail.
    """
    valor = normalizar_usuario(email)
    try:
        re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", valor).group()
    except AttributeError:
        raise ValueError('Informe um e-mail válido, por exemplo seu endereço Gmail de teste.') from None
    return valor
