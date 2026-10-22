class ErroBancoDeDados(Exception):
    """Erro de infraestrutura do banco, sem vazar detalhes do driver."""


class ErroIndexacao(Exception):
    """Documento que não pôde ser indexado (ilegível, sem texto extraível, etc.)."""


class ErroGeracaoResposta(Exception):
    """Falha do provedor de geração, sem expor credenciais ou conteúdo."""


class ErroBusca(Exception):
    """Falha de leitura do índice ou do embedding."""


class ErroOcupado(Exception):
    """Capacidade de atendimento esgotada."""


class ErroPrazo(Exception):
    """Prazo total excedido, incluindo espera."""
