import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from dominio.erros import ErroEnvioMensagem
from dominio.mensageiro import Handler, MensagemRecebida, Mensageiro

logger = logging.getLogger(__name__)


class TelegramGateway(Mensageiro):
    _LIMITE = 4096
    _MSG_ERRO = "Algo deu errado. Tente novamente em instantes."
    _MSG_BOAS_VINDAS = (
        "Olá! Sou o consultor virtual da faculdade. "
        "Envie sua dúvida em texto que eu ajudo você."
    )
    _MSG_SO_TEXTO = "No momento só consigo entender mensagens de texto."

    def __init__(self, token_bot: str):
        # O httpx loga a URL das requisições em INFO, e o token vai nela.
        logging.getLogger("httpx").setLevel(logging.WARNING)

        # concurrent_updates: sem isso o Telegram processa uma mensagem por vez,
        # e uma resposta lenta (LLM + banco) travaria o atendimento de todos.
        self._app = (
            Application.builder().token(token_bot).concurrent_updates(True).build()
        )
        self._handler: Handler | None = None

        self._app.add_handler(CommandHandler("start", self._processar_start))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._processar_update)
        )
        self._app.add_handler(
            MessageHandler(
                ~filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
                self._processar_nao_texto,
            )
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

    async def _enviar_sem_falhar(self, chat_id: int, texto: str) -> None:
        """Envio para avisos do próprio gateway: registra a falha, mas não propaga."""
        try:
            await self.enviar_mensagem(chat_id, texto)
        except ErroEnvioMensagem:
            logger.exception("Não foi possível enviar mensagem ao usuário")

    async def _processar_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message is None:
            return
        await self._enviar_sem_falhar(update.message.chat_id, self._MSG_BOAS_VINDAS)

    async def _processar_nao_texto(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message is None:
            return
        await self._enviar_sem_falhar(update.message.chat_id, self._MSG_SO_TEXTO)

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
            await self._enviar_sem_falhar(chat_id, self._MSG_ERRO)

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
        pedacos.append(restante)
        # O Telegram rejeita mensagens só com espaços/quebras de linha.
        return [p for p in pedacos if p.strip()]


if __name__ == "__main__":
    import os

    gateway = TelegramGateway(os.environ["TELEGRAM_BOT_TOKEN"])

    async def eco(msg: MensagemRecebida) -> None:
        await gateway.enviar_mensagem(msg.chat_id, f"Você disse: {msg.texto}")

    gateway.ao_receber(eco)
    gateway.iniciar()
