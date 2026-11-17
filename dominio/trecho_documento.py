from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TrechoDocumento:
    arquivo: str
    pagina: int | None
    texto: str
    similaridade: float = 0.0
    documento_id: str = ''
    versao_id: str = ''
    curso: str = ''
    periodo: str = ''
    ano: int | None = None
    inicio: date | None = None
    fim: date | None = None
    url_oficial: str = ''

    @property
    def rotulo(self):
        """Retorne nome do documento e página, quando disponível, para citação."""
        return f'{self.arquivo}, p. {self.pagina}' if self.pagina else self.arquivo
