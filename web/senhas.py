import hashlib
import hmac
import secrets


def derivar(senha, sal):
    """Derive 32 bytes de senha usando scrypt e sal individual."""
    return hashlib.scrypt(senha.encode(), salt=sal, n=16384, r=8, p=1, dklen=32)


def gerar_hash(senha):
    """Retorne hash scrypt com sal aleatório para senha de 12 a 256 caracteres.
    
    Args:
        senha: Senha recebida em memória; nunca registrada em log.
    
    Returns:
        String com algoritmo, sal e hash.
    """
    if not 12 <= len(senha) <= 256:
        raise ValueError('Use uma senha de 12 a 256 caracteres.')
    sal = secrets.token_bytes(16)
    return 'scrypt$' + sal.hex() + '$' + derivar(senha, sal).hex()


def conferir(senha, guardado):
    """Compare senha e hash em tempo constante; retorne falso para formato inválido.
    
    Args:
        senha: Senha recebida em memória; nunca registrada em log.
        guardado: Hash scrypt previamente configurado no servidor.
    
    Returns:
        True somente se a senha corresponder ao hash.
    """
    try:
        algoritmo, sal, valor = guardado.split('$')
        if algoritmo != 'scrypt' or len(sal) != 32 or len(valor) != 64:
            return False
        return hmac.compare_digest(derivar(senha, bytes.fromhex(sal)), bytes.fromhex(valor))
    except (ValueError, TypeError):
        return False
