"""Publicação dos documentos reais presentes na pasta documentos."""
from aplicacao.dominio.metadados import Metadados
from aplicacao.servicos.acervo.documentos_reais import manifesto


def validar_fontes():
    """Consulte os PDFs atuais antes de iniciar qualquer publicação.

    Returns:
        list[dict]: Arquivos reais com hashes e metadados.
    """
    return manifesto()['fontes']


def publicar(base, fonte, forcar=False):
    """Publique somente um conteúdo novo ou explicitamente solicitado.

    Args:
        base: Base de conhecimento selecionada na configuração.
        fonte (dict): Descrição atual do PDF institucional.
        forcar (bool): Solicita reconstruir inclusive conteúdo idêntico.

    Returns:
        int: Quantidade publicada; zero quando a versão continua igual.
    """
    igual = base.repositorio.indexado(fonte['sha256'], base._modelo_embedding, fonte['arquivo'])
    if igual and not forcar:
        return 0
    meta = Metadados(curso=fonte['curso'], url_oficial=fonte['url_oficial'])
    return base.indexar_arquivo(fonte['caminho'], forcar=forcar, metadados=meta)


def carregar_iniciais(base, forcar=False):
    """Compare os PDFs atuais e publique cada documento atomicamente.

    Args:
        base: Base vinculada ao repositório persistente.
        forcar (bool): Reindexa também PDFs idênticos.

    Returns:
        dict: Nome do PDF e quantidade de trechos publicados.
    """
    return {f['arquivo']: publicar(base, f, forcar) for f in validar_fontes()}
