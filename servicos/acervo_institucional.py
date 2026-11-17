"""Carga explícita dos PPCs e das perguntas frequentes da secretaria."""
from pathlib import Path
from dominio.metadados import Metadados
from dominio.erros import ErroIndexacao
from servicos.base_conhecimento import hash_arquivo
from servicos.documentos_reais import manifesto, retirar_exemplos

DADOS = Path(__file__).resolve().parents[1] / 'dados'


def validar_fontes():
    """Confirme a integridade de todas as fontes antes de iniciar a carga.

    Returns:
        list: Descrições das fontes verificadas.

    Raises:
        ErroIndexacao: Se algum arquivo divergir da revisão incluída.
    """
    fontes = manifesto()['fontes']
    for fonte in fontes:
        try:
            (True,).index(hash_arquivo(DADOS / fonte['arquivo']) == fonte['sha256'])
        except ValueError:
            raise ErroIndexacao('Fonte alterada; revise o documento antes de atualizar o manifesto.') from None
    return fontes


def publicar(base, fonte, forcar=False):
    """Publique uma fonte com seus metadados, evitando embeddings repetidos.

    Args:
        base: Base de conhecimento de destino.
        fonte (dict): Documento validado no manifesto.
        forcar (bool): Solicita nova indexação mesmo se a versão for idêntica.

    Returns:
        int: Número de trechos publicados.
    """
    igual = base.repositorio.indexado(fonte['sha256'], base._modelo_embedding, fonte['arquivo'])
    try:
        (True,).index(forcar or not igual)
    except ValueError:
        return 0
    meta = Metadados(curso=fonte['curso'], url_oficial=fonte['url_oficial'])
    return base.indexar_arquivo(DADOS / fonte['arquivo'], forcar=forcar, metadados=meta)


def carregar_iniciais(base, forcar=False):
    """Retire exemplos conhecidos e publique as fontes reais na base escolhida.

    Args:
        base: Base vinculada ao repositório da aplicação.
        forcar (bool): Solicita reindexação das fontes incluídas.

    Returns:
        dict: Arquivo e quantidade de trechos publicados.
    """
    fontes = validar_fontes()
    retirar_exemplos(base.repositorio)
    return {f['arquivo']: publicar(base, f, forcar) for f in fontes}
