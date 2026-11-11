"""Primeira publicação e retomada após falhas, sempre usando Gemini."""
import logging
import time
from infra.inicializacao import carga_concluida, registrar_carga
from servicos.acervo_institucional import carregar_iniciais
from servicos.prazo import FIM
from infra.retomada_lotes import memorizar_lotes

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
    """Carregue os PPCs e a FAQ apenas antes da primeira conclusão.

    Args:
        engine: Banco com marcador persistente de inicialização.
        base: Base de conhecimento ligada ao Gemini.

    Returns:
        dict: Trechos publicados, ou vazio quando o acervo já foi preparado.
    """
    try:
        (True,).index(carga_concluida(engine, getattr(base, 'chave_carga', 'acervo_inicial')))
    except ValueError:
        logger.warning('Preparando PPCs e FAQ: busca %s.', getattr(base, 'chave_carga', 'vetorial Gemini'))
        return publicar_iniciais(engine, base)
    return {}
