from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class MensagemRecebida:
    chat_id: int
    usuario_id: int  # id do canal (ex.: Telegram), não é o RA do aluno
    texto: str


Handler = Callable[[MensagemRecebida], Awaitable[None]]


class Mensageiro(ABC):
    """Porta de entrada/saída de mensagens, independente do canal."""

    @abstractmethod
    def ao_receber(self, handler: Handler) -> None: ...

    @abstractmethod
    async def enviar_mensagem(self, chat_id: int, texto: str) -> None: ...

    @abstractmethod
    def iniciar(self) -> None: ...
