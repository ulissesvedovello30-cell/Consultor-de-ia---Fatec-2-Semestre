class ErroBancoDeDados(Exception):
    """Erro de infraestrutura do banco, sem vazar detalhes do driver."""


class ErroEnvioMensagem(Exception):
    """Falha ao enviar mensagem pelo canal, sem vazar detalhes da biblioteca."""
