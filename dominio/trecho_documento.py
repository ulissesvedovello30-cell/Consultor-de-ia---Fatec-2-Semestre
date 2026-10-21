from dataclasses import dataclass


@dataclass(frozen=True)
class TrechoDocumento:
    """Pedaço de um documento. `pagina` é None em formatos sem página (DOCX, TXT);
    `similaridade` só vale em resultado de busca."""

    arquivo: str
    pagina: int | None
    texto: str
    similaridade: float = 0.0

    @property
    def rotulo(self) -> str:
        """Como a fonte aparece para o aluno: 'arquivo, p. 3' ou só 'arquivo'."""
        return f"{self.arquivo}, p. {self.pagina}" if self.pagina else self.arquivo
