"""Interfaces pequenas para injetar armazenamento e verificação de credenciais."""
from typing import Protocol


class ArmazemLogin(Protocol):
    """Contrato persistente exigido pelo serviço de autenticação."""

    def reservar(self, chaves: tuple[str, ...], agora: float) -> None:
        """Reserve atomicamente uma tentativa ou lance TentativasExcedidas."""
        ...

    def consumir_codigo(self, chave: str, passo: int) -> bool:
        """Aceite somente um passo TOTP maior que todos os já usados pela conta."""
        ...


class TentativasExcedidas(Exception):
    """Tentativa recusada antes da verificação custosa da senha."""

    def __init__(self, segundos):
        """Receba o tempo mínimo de espera sem guardar identificadores pessoais."""
        self.segundos = max(1, int(segundos))
        super().__init__('Aguarde antes de tentar novamente.')


class FalhaSeguranca(Exception):
    """Infraestrutura de proteção indisponível: autenticação deve falhar fechada."""


class CredenciaisInvalidas(Exception):
    """Mensagem genérica para senha, conta ou segundo fator incorretos."""


class LoginIndisponivel(Exception):
    """Administração incompletamente configurada ou capacidade ocupada."""
