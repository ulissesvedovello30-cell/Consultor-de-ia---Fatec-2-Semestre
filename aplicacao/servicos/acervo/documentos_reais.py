"""Descoberta dos PDFs institucionais e minimização antes da publicação."""
import hashlib
from aplicacao.configuracao.caminhos import DOCUMENTOS
from aplicacao.dominio.erros import ErroIndexacao
from aplicacao.servicos.respostas.politica import PESSOAIS


def fontes_locais():
    """Liste PDFs reais sem depender de um catálogo antigo.

    Returns:
        list[Path]: Arquivos ordenados, encontrados nas subpastas de documentos.

    Raises:
        ErroIndexacao: Quando não houver fontes ou existirem nomes repetidos.
    """
    fontes = sorted(p for p in DOCUMENTOS.rglob('*') if p.suffix.lower() in {'.pdf', '.txt', '.docx'})
    nomes = [p.name.casefold() for p in fontes]
    if not fontes or len(nomes) != len(set(nomes)):
        raise ErroIndexacao('Inclua PDFs ou documentos TXT/DOCX com nomes únicos na pasta documentos.')
    return fontes


def descrever_fonte(caminho):
    """Identifique conteúdo e curso a partir da organização das fontes.

    Args:
        caminho (Path): PDF institucional localizado no projeto.

    Returns:
        dict: Identidade atual do arquivo e curso para delimitar a consulta.
    """
    pasta = caminho.parent.name.lower()
    curso = {'ia': 'IA', 'esg': 'ESG'}.get(pasta, '')
    return dict(arquivo=caminho.name, caminho=caminho,
                sha256=hashlib.sha256(caminho.read_bytes()).hexdigest(), curso=curso, url_oficial='')


def manifesto():
    """Descreva os PDFs presentes, calculando os hashes dos bytes atuais.

    Returns:
        dict: Fontes institucionais efetivamente disponíveis.
    """
    try:
        return {'fontes': [descrever_fonte(p) for p in fontes_locais()]}
    except OSError:
        raise ErroIndexacao('Não foi possível ler os PDFs institucionais.') from None


def conferir_documento(hash_documento):
    """Valide o resumo recebido sem depender dos documentos de demonstração.

    Args:
        hash_documento (str): SHA-256 do documento a publicar.

    Raises:
        ErroIndexacao: Quando o resumo não representa um SHA-256.
    """
    try:
        bytes.fromhex(hash_documento)
        (True,).index(len(hash_documento) == 64)
    except (ValueError, TypeError):
        raise ErroIndexacao('Identidade documental inválida.') from None


def preparar_paginas(caminho, paginas):
    """Oculte identificadores nos PDFs institucionais locais antes do RAG.

    Args:
        caminho (Path): Origem validada pelo parser protegido.
        paginas (list): Pares de página e texto extraído.

    Returns:
        list: Páginas minimizadas; uploads continuam sujeitos à recusa de dados pessoais.
    """
    try:
        caminho.resolve().relative_to(DOCUMENTOS.resolve())
    except ValueError:
        return paginas
    return [(n, PESSOAIS.sub('[identificador omitido]', t)) for n, t in paginas]


def retirar_exemplos(repositorio):
    """Mantenha compatibilidade com a composição sem inserir exemplos no acervo.

    Args:
        repositorio: Repositório vigente; os bancos antigos não acompanham a entrega.

    Returns:
        int: Zero, pois somente as fontes presentes são publicadas na base nova.
    """
    return 0
