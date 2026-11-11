"""Configure uma conta administrativa local identificada por e-mail."""
from getpass import getpass
from pathlib import Path
from dotenv import set_key
from web.senhas import gerar_hash
from seguranca.identidade_admin import validar_email


def ler_senha():
    """Leia e confirme uma senha própria do aplicativo, sem exibi-la.

    Returns:
        str: Senha confirmada em memória.

    Raises:
        ValueError: Se a confirmação não corresponder à senha.
    """
    senha = getpass('Senha do aplicativo (mínimo 12 caracteres; não use a senha do Gmail): ')
    try:
        (True,).index(senha == getpass('Confirme a senha: '))
    except ValueError:
        raise ValueError('As senhas não conferem.') from None
    return senha


def main():
    """Configure o e-mail e o hash da senha sem criar cadastro remoto aberto."""
    usuario = validar_email(input('E-mail do administrador (pode ser seu Gmail de teste): '))
    salvar(usuario, gerar_hash(ler_senha()))
    print('Administrador configurado. Reinicie o servidor para aplicar.')
    print('Configure também o autenticador obrigatório: python configurar_2fa.py')


def salvar(usuario, hash_senha):
    """Grave a conta local preservando as demais configurações do servidor.

    Args:
        usuario (str): E-mail validado do administrador.
        hash_senha (str): Hash scrypt; nunca uma senha em texto simples.

    Raises:
        OSError: Se o arquivo não puder ser gravado.
    """
    caminho = Path(__file__).parent / '.env'
    caminho.touch(mode=0o600, exist_ok=True)
    caminho.chmod(0o600)
    set_key(caminho, 'ADMIN_USUARIO', validar_email(usuario))
    set_key(caminho, 'ADMIN_SENHA_HASH', hash_senha)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt):
        print('Não foi possível configurar o administrador. Confira as entradas e permissões.')
        raise SystemExit(1) from None
