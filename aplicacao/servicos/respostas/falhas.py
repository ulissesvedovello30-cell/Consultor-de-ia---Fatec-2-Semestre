"""Tradução de falhas remotas para os resultados públicos do atendimento."""
from aplicacao.dominio.erros import ErroGeracaoResposta, ErroLimiteProvedor, ErroPrazo
from aplicacao.infra.gemini.gemini_http import ErroCotaGemini


def falha_geracao(erro):
    """Diferencie cota, prazo e outras falhas antes de apresentar o resultado.

    Args:
        erro (Exception): Falha do gerador ou do transporte.

    Returns:
        Exception: Exceção de domínio sem credenciais ou conteúdo do provedor.
    """
    if isinstance(erro, TimeoutError):
        return ErroPrazo('Tempo da geração excedido.')
    if isinstance(erro, ErroCotaGemini):
        return ErroLimiteProvedor('Limite do provedor atingido.')
    return ErroGeracaoResposta('Falha ao gerar a resposta.')
