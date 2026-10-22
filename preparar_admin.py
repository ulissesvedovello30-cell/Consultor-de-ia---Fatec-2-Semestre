from getpass import getpass
from pathlib import Path
from dotenv import set_key
from web.senhas import gerar_hash


def main():
    """Execute a configuração interativa do administrador, sem registrar a senha."""
    usuario = input('Nome do administrador: ').strip()
    if not usuario or len(usuario) > 100:
        raise ValueError('Nome deve ter de 1 a 100 caracteres.')
    senha = getpass('Nova senha (mínimo 12 caracteres): ')
    if senha != getpass('Confirme a senha: '):
        raise ValueError('As senhas não conferem.')
    salvar(usuario, gerar_hash(senha))
    print('Administrador configurado. Reinicie o servidor para aplicar.')


def salvar(usuario, hash_senha):
    """Grave usuário e hash da senha no .env local, preservando demais configurações."""
    caminho = Path(__file__).parent / '.env'
    set_key(caminho, 'ADMIN_USUARIO', usuario)
    set_key(caminho, 'ADMIN_SENHA_HASH', hash_senha)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as erro:
        print(f'Não foi possível configurar: {erro}')
