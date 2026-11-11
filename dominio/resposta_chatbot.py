from dataclasses import dataclass


@dataclass(frozen=True)
class RespostaChatbot:
    texto: str
    sucesso: bool
    similaridade: float
    fontes: tuple = ()
    estado: str = 'respondida'

    @property
    def score_qualidade(self):
        """Compatibilidade do terminal antigo; o valor é similaridade, não confiança."""
        return self.similaridade
