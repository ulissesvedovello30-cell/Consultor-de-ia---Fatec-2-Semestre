"""TOTP RFC 6238 (SHA-1, seis dígitos, janela de 30 segundos)."""
import base64
import hashlib
import hmac
import re
import struct


def chave_binaria(segredo):
    """Decodifique segredo Base32 de pelo menos 160 bits ou lance ValueError."""
    bruto = base64.b32decode(segredo.upper(), casefold=True)
    if len(bruto) < 20:
        raise ValueError('Segredo TOTP muito curto.')
    return bruto


def codigo(segredo, passo, digitos=6):
    """Retorne HOTP para um contador temporal; digitos=8 permite vetores RFC."""
    digest = hmac.new(chave_binaria(segredo), struct.pack('>Q', passo), hashlib.sha1).digest()
    inicio = digest[-1] & 15
    numero = struct.unpack('>I', digest[inicio:inicio + 4])[0] & 0x7fffffff
    return str(numero % (10 ** digitos)).zfill(digitos)


def verificar(segredo, recebido, agora):
    """Retorne o passo correspondente em ±30 s ou None, sem consumir o código."""
    if not re.fullmatch(r'[0-9]{6}', recebido):
        return None
    passo = int(agora // 30)
    for candidato in (passo, passo - 1, passo + 1):
        if candidato >= 0 and hmac.compare_digest(codigo(segredo, candidato), recebido):
            return candidato
    return None
