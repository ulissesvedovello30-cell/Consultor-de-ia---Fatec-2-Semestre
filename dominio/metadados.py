from dataclasses import dataclass, asdict
from datetime import date
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Metadados:
    curso: str = ''
    periodo: str = ''
    ano: int | None = None
    inicio: date | None = None
    fim: date | None = None
    url_oficial: str = ''

    def __post_init__(self):
        """Valide a configuração construída e lance ValueError se os parâmetros forem inválidos."""
        if len(self.curso) > 160 or len(self.periodo) > 80:
            raise ValueError('Curso ou período muito longo.')
        if self.ano is not None and not 2000 <= self.ano <= 2100:
            raise ValueError('Ano deve estar entre 2000 e 2100.')
        if self.inicio and self.fim and self.inicio > self.fim:
            raise ValueError('Início da vigência deve anteceder o fim.')
        validar_url(self.url_oficial)

    def valores(self):
        """Retorne os metadados como dicionário para persistência."""
        return asdict(self)


def validar_url(url):
    """Aceite URL vazia ou HTTPS sem credenciais; lance ValueError nas demais entradas."""
    if not url:
        return
    partes = urlsplit(url)
    if len(url) > 1000 or partes.scheme != 'https' or not partes.hostname:
        raise ValueError('A URL oficial deve ser HTTPS.')
    if partes.username or partes.password or any(c.isspace() for c in url):
        raise ValueError('URL oficial inválida.')
