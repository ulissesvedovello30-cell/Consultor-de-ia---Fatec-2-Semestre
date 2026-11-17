"""Identificação do acervo revisado e minimização do texto dos PPCs."""
import hashlib
import json
from pathlib import Path
from dominio.erros import ErroIndexacao
from servicos.politica import PESSOAIS

MANIFESTO = Path(__file__).resolve().parents[1] / 'dados/acervo.json'


def manifesto():
    """Leia as identidades das fontes incluídas no projeto.

    Returns:
        dict: Fontes revisadas e hashes dos exemplos retirados.

    Raises:
        ErroIndexacao: Se o manifesto estiver indisponível ou inválido.
    """
    try:
        return json.loads(MANIFESTO.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ErroIndexacao('Manifesto do acervo indisponível.') from None


def conferir_documento(hash_documento):
    """Recuse a republicação dos arquivos fictícios conhecidos.

    Args:
        hash_documento (str): SHA-256 dos bytes recebidos.

    Raises:
        ErroIndexacao: Se os bytes forem de um exemplo retirado.
    """
    try:
        manifesto()['hashes_ficticios_removidos'].index(hash_documento)
    except ValueError:
        return
    raise ErroIndexacao('Documento fictício retirado do acervo. Envie uma fonte real.')


def preparar_paginas(caminho, paginas):
    """Oculte identificadores somente nos PPCs revisados e conhecidos por hash.

    Args:
        caminho (Path): Documento extraído pelo parser protegido.
        paginas (list): Pares de página e texto original.

    Returns:
        list: Texto minimizado, com os números de página preservados.
    """
    digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
    revisados = {f['sha256'] for f in manifesto()['fontes'] if f['arquivo'].endswith('.pdf')}
    try:
        (True,).index(digest in revisados)
    except ValueError:
        return paginas
    return [(numero, PESSOAIS.sub('[identificador omitido]', texto)) for numero, texto in paginas]


def retirar_exemplos(repositorio):
    """Exclua versões e vetores dos exemplos conhecidos, preservando outros documentos.

    Args:
        repositorio: Repositório persistente com listar e excluir.

    Returns:
        int: Quantidade de documentos removidos.
    """
    hashes = set(manifesto()['hashes_ficticios_removidos'])
    antigos = [d for d in repositorio.listar() if d['hash_arquivo'] in hashes]
    return sum(bool(repositorio.excluir(d['documento_id'])) for d in antigos)
