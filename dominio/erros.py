class ErroBancoDeDados(Exception):
    """Erro de infraestrutura do banco, sem vazar detalhes do driver."""


class ErroEnvioMensagem(Exception):
    """Falha ao enviar mensagem pelo canal, sem vazar detalhes da biblioteca."""


class ErroIndexacao(Exception):
    """PDF que não pôde ser indexado (ilegível, sem texto extraível, etc.)."""


class ErroGeracaoResposta(Exception):
    """Falha do modelo local ao gerar a resposta, sem vazar detalhes da biblioteca."""
