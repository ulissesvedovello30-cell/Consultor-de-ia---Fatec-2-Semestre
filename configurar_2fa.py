"""Configure o segundo fator localmente, sem oferecer cadastro remoto de segredos."""
import base64
import secrets
import time
from getpass import getpass
from pathlib import Path
from urllib.parse import quote, urlencode
from dotenv import dotenv_values, set_key
from seguranca.totp import verificar


def preparar(caminho):
    """Leia usuário local e confirme explicitamente a rotação de segredo existente."""
    valores = dotenv_values(caminho)
    if valores.get('ADMIN_TOTP_SECRET') and input('Substituir o segundo fator? Digite SIM: ') != 'SIM':
        raise ValueError('Configuração cancelada; segredo anterior preservado.')
    usuario = valores.get('ADMIN_USUARIO') or 'admin'
    segredo = base64.b32encode(secrets.token_bytes(20)).decode('ascii')
    return usuario, segredo


def apresentar(usuario, segredo):
    """Exiba somente no terminal local os dados para cadastrar o autenticador."""
    parametros = urlencode({'secret': segredo, 'issuer': 'Consultor Fatec', 'period': 30, 'digits': 6})
    uri = 'otpauth://totp/' + quote('Consultor Fatec:' + usuario, safe='') + '?' + parametros
    print('Cadastre uma conta TOTP no seu autenticador (6 dígitos, 30 segundos).')
    print('Chave manual:', segredo)
    print('URI de cadastro:', uri)
    print('Não compartilhe nem fotografe este terminal. Guarde recuperação em local seguro.')


def main():
    """Gere segredo e grave no .env somente depois de comprovar o código TOTP."""
    caminho = Path(__file__).resolve().parent / '.env'
    usuario, segredo = preparar(caminho)
    apresentar(usuario, segredo)
    if verificar(segredo, getpass('Código atual do autenticador: ').strip(), time.time()) is None:
        raise ValueError('Código inválido; nada foi gravado. Confira o relógio.')
    set_key(caminho, 'ADMIN_TOTP_SECRET', segredo)
    caminho.chmod(0o600)
    print('Segundo fator configurado. Reinicie o servidor para revogar sessões anteriores.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyboardInterrupt):
        print('Não foi possível concluir a configuração do segundo fator.')
