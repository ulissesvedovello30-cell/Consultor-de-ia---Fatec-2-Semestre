import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)


class ErroEnvioMensagem(Exception):
    """Falha ao enviar mensagem pelo canal, sem vazar detalhes da biblioteca."""


@dataclass(frozen=True)
class MensagemRecebida:
    chat_id: int
    usuario_id: int  # id do Telegram, não é a matrícula
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


class TelegramGateway(Mensageiro):
    _LIMITE = 4096
    _MSG_ERRO = "Algo deu errado. Tente novamente em instantes."

    def __init__(self, token_bot: str):
        # O httpx loga a URL das requisições em INFO, e o token vai nela.
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self._app = Application.builder().token(token_bot).build()
        self._handler: Handler | None = None
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._processar_update)
        )

    def ao_receber(self, handler: Handler) -> None:
        self._handler = handler

    def iniciar(self) -> None:
        self._app.run_polling()

    async def enviar_mensagem(self, chat_id: int, texto: str) -> None:
        if not texto.strip():
            return  # o Telegram rejeita mensagens vazias
        try:
            for pedaco in self._dividir(texto):
                await self._app.bot.send_message(chat_id=chat_id, text=pedaco)
        except TelegramError as e:
            raise ErroEnvioMensagem("Falha ao enviar mensagem") from e

    async def _processar_update(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if (
            self._handler is None
            or update.message is None
            or update.message.text is None
            or update.effective_user is None
        ):
            return

        chat_id = update.message.chat_id
        try:
            await self._handler(
                MensagemRecebida(
                    chat_id=chat_id,
                    usuario_id=update.effective_user.id,
                    texto=update.message.text,
                )
            )
        except Exception:
            # Não loga o conteúdo da mensagem (dados pessoais / LGPD).
            logger.exception("Erro ao tratar mensagem")
            try:
                await self.enviar_mensagem(chat_id, self._MSG_ERRO)
            except ErroEnvioMensagem:
                logger.exception("Não foi possível avisar o usuário sobre o erro")

    def _dividir(self, texto: str) -> list[str]:
        """Quebra o texto em pedaços de até _LIMITE, preferindo quebras de linha."""
        pedacos: list[str] = []
        restante = texto
        while len(restante) > self._LIMITE:
            corte = restante.rfind("\n", 0, self._LIMITE)
            if corte <= 0:
                corte = self._LIMITE
            pedacos.append(restante[:corte])
            restante = restante[corte:].lstrip("\n")
        if restante.strip():
            pedacos.append(restante)
        return pedacos


if __name__ == "__main__":
    import os

    gateway = TelegramGateway(os.environ["TELEGRAM_BOT_TOKEN"])

    async def eco(msg: MensagemRecebida) -> None:
        await gateway.enviar_mensagem(msg.chat_id, f"Você disse: {msg.texto}")

    gateway.ao_receber(eco)
    gateway.iniciar()