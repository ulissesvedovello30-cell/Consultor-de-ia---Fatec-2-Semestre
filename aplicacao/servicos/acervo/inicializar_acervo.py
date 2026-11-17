"""Primeira publicação e retomada após falhas, sempre usando Gemini."""
import logging
import time
from aplicacao.infra.persistencia.inicializacao import carga_concluida, registrar_carga
from aplicacao.servicos.acervo.acervo_institucional import carregar_iniciais, validar_fontes
from aplicacao.infra.persistencia.sincronizacao import retirar_ausentes
from aplicacao.servicos.respostas.prazo import FIM
from aplicacao.infra.gemini.retomada_lotes import memorizar_lotes

logger = logging.getLogger(__name__)


def publicar_iniciais(engine, base, forcar=False):
    """Publique fontes e registre sucesso somente após concluir todas.

    Args:
        engine: Banco persistente preparado.
        base: Base com embeddings Gemini no aplicativo.
        forcar (bool): Reprocesse inclusive arquivos idênticos.

    Returns:
        dict: Quantidade publicada por arquivo.
    """
    token = FIM.set(time.monotonic() + 900)
    try:
        with memorizar_lotes(None if forcar else engine):
            resultado = carregar_iniciais(base, forcar)
        registrar_carga(engine, getattr(base, 'chave_carga', 'acervo_inicial'))
        return resultado
    finally:
        FIM.reset(token)


def preparar_primeira_carga(engine, base):
    """Sincronize PDFs novos, alterados ou removidos a cada inicialização.

    Args:
        engine: Banco com marcador persistente de inicialização.
        base: Base de conhecimento ligada ao Gemini.

    Returns:
        dict: Trechos publicados, ou vazio quando o acervo já foi preparado.
    """
    logger.info('Conferindo PPCs e calendário acadêmico nos PDFs locais.')
    resultado = publicar_iniciais(engine, base)
    retirar_ausentes(engine, base, {f['arquivo'] for f in validar_fontes()})
    return resultado
