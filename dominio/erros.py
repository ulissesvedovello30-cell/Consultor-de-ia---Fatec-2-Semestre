class ErroBancoDeDados(Exception):
    """Erro de infraestrutura do banco, sem vazar detalhes do driver."""


class ErroIndexacao(Exception):
    """Documento que não pôde ser indexado (ilegível, sem texto extraível, etc.)."""


class ErroGeracaoResposta(Exception):
    """Falha do modelo local ao gerar a resposta, sem vazar detalhes da biblioteca."""
