import asyncio
import logging
from contextlib import asynccontextmanager

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


class _OcultaToken(logging.Filter):
    """Troca o token do bot por *** nas mensagens de log.

    O httpx loga a URL das requisições (e o token vai nela). Em vez de silenciar o
    logger inteiro, só o token é ocultado e o resto continua visível.
    """

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if self._token and self._token in record.getMessage():
            record.msg = record.getMessage().replace(self._token, "***")
            record.args = ()
        return True


class TelegramGateway(Mensageiro):
    _LIMITE = 4096  # medido em unidades UTF-16, como o Telegram conta
    _MSG_ERRO = "Algo deu errado. Tente novamente em instantes."
    _MSG_BOAS_VINDAS = (
        "Olá! Sou o consultor virtual da faculdade. "
        "Envie sua dúvida em texto que eu ajudo você."
    )
    _MSG_SO_TEXTO = "No momento só consigo entender mensagens de texto."

    def __init__(self, token_bot: str):
        logging.getLogger("httpx").addFilter(_OcultaToken(token_bot))

        # concurrent_updates: sem isso o Telegram processa uma mensagem por vez,
        # e uma resposta lenta (LLM + banco) travaria o atendimento de todos.
        self._app = (
            Application.builder().token(token_bot).concurrent_updates(True).build()
        )
        self._handler: Handler | None = None
        # chat_id -> [lock, quantidade de mensagens esperando/em processamento]
        self._travas: dict[int, list] = {}

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

    @asynccontextmanager
    async def _serializar(self, chat_id: int):
        """Garante uma mensagem por vez em cada conversa (usuários diferentes seguem em paralelo).

        Evita respostas fora de ordem e duas mensagens do mesmo aluno mexendo
        ao mesmo tempo no mesmo estado (ex.: a sessão).
        """
        entrada = self._travas.get(chat_id)
        if entrada is None:
            entrada = self._travas[chat_id] = [asyncio.Lock(), 0]
        entrada[1] += 1
        try:
            async with entrada[0]:
                yield
        finally:
            entrada[1] -= 1
            if entrada[1] == 0:
                self._travas.pop(chat_id, None)

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
        async with self._serializar(chat_id):
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

    @classmethod
    def _caracteres_que_cabem(cls, texto: str) -> int:
        """Quantos caracteres do início do texto cabem no limite, contando em UTF-16
        (emoji fora do plano básico vale 2)."""
        unidades = 0
        for i, ch in enumerate(texto):
            unidades += 2 if ord(ch) > 0xFFFF else 1
            if unidades > cls._LIMITE:
                return i
        return len(texto)

    def _dividir(self, texto: str) -> list[str]:
        """Quebra o texto em pedaços que cabem no limite, preferindo quebras de linha.

        Só a quebra de linha usada como ponto de corte é descartada; linhas em branco
        e o restante da formatação são preservados.
        """
        pedacos: list[str] = []
        restante = texto
        while True:
            limite = self._caracteres_que_cabem(restante)
            if limite >= len(restante):
                break
            corte = restante.rfind("\n", 0, limite)
            if corte > 0:
                pedacos.append(restante[:corte])
                restante = restante[corte + 1 :]
            else:
                pedacos.append(restante[:limite])
                restante = restante[limite:]
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
