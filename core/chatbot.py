import logging
import re
import time

from core.limitador import LimitadorTaxa
from dominio.erros import ErroGeracaoResposta
from dominio.resposta_chatbot import RespostaChatbot

logger = logging.getLogger(__name__)


class Chatbot:
    """Orquestra a conversa: comandos, limites e a ponte até o RAG.

    Não conhece o canal (site, terminal...) nem o banco. Quem integra chama
    `processar_mensagem` com um identificador de conversa e o texto. O identificador é
    só um código opaco, usado para o limite de perguntas e para lembrar a pergunta
    anterior; nada sobre a pessoa é guardado, e tudo fica em memória.
    """

    AJUDA = (
        "Olá! Sou o consultor virtual da faculdade. Pergunte sobre o calendário de aulas, "
        "as provas marcadas e os eventos da Fatec.\n\n"
        "/ajuda — ver esta mensagem\n\n"
        "As respostas são geradas por IA a partir dos documentos da turma. "
        "Confira data, horário e local com a secretaria antes de agir."
    )
    MAX_CARACTERES = 1500
    SEGUNDOS_DE_CONTEXTO = 600  # quanto tempo a pergunta anterior fica na memória

    _SAUDACAO = re.compile(r"(oi+|ol[aá]|e a[ií]|bom dia|boa tarde|boa noite|hello|hey)[\s!.?]*", re.IGNORECASE)
    _REFERE_ANTERIOR = re.compile(r"\b(isso|disso|esse|essa|desse|dessa|nele|nela)\b", re.IGNORECASE)

    def __init__(
        self,
        consultor,
        limitador: LimitadorTaxa | None = None,
        max_simultaneos: int = 8,
        relogio=time.monotonic,
    ):
        self._consultor = consultor
        self._limitador = limitador or LimitadorTaxa(limite=6, janela=60)
        self._max_simultaneos = max_simultaneos
        self._relogio = relogio
        # O modelo local responde uma pergunta por vez; sem teto, a fila de espera cresce sem fim.
        self._em_atendimento = 0
        # conversa -> (quando, pergunta). Só em memória: reiniciar o bot esquece tudo.
        self._ultima_pergunta: dict[str, tuple[float, str]] = {}

    async def processar_mensagem(self, conversa_id: str, texto: str) -> RespostaChatbot:
        texto = texto.strip()
        if not texto or len(texto) > self.MAX_CARACTERES:
            return RespostaChatbot(f"Envie uma pergunta entre 1 e {self.MAX_CARACTERES} caracteres.", False, 0.0)

        comando = texto.split()[0].lower().split("@")[0]
        if comando in {"/start", "/ajuda"} or self._SAUDACAO.fullmatch(texto):
            return RespostaChatbot(self.AJUDA, True, 0.0)
        if comando.startswith("/"):
            return RespostaChatbot("Comando desconhecido. Use /ajuda.", False, 0.0)

        if self._em_atendimento >= self._max_simultaneos:
            return RespostaChatbot("Atendimento ocupado. Tente novamente em instantes.", False, 0.0)
        if not self._limitador.permitir(conversa_id):
            return RespostaChatbot("Limite de 6 perguntas por minuto. Aguarde um pouco.", False, 0.0)

        self._em_atendimento += 1
        try:
            resposta = await self._consultor.responder(self._com_contexto(conversa_id, texto))
        except ErroGeracaoResposta:
            logger.warning("Falha do modelo ao gerar a resposta")
            return RespostaChatbot("Não consegui gerar a resposta agora. Tente novamente em instantes.", False, 0.0)
        finally:
            self._em_atendimento -= 1

        if resposta.encontrou:
            self._ultima_pergunta[conversa_id] = (self._relogio(), texto)
        score = max(0.0, min(1.0, resposta.melhor_similaridade))
        return RespostaChatbot(resposta.texto_com_fontes(), resposta.encontrou, score)

    def _com_contexto(self, conversa_id: str, texto: str) -> str:
        """Perguntas como 'e disso, quando é?' só fazem sentido com a pergunta anterior."""
        agora = self._relogio()
        self._ultima_pergunta = {c: v for c, v in self._ultima_pergunta.items() if agora - v[0] < self.SEGUNDOS_DE_CONTEXTO}
        anterior = self._ultima_pergunta.get(conversa_id)
        if anterior and self._REFERE_ANTERIOR.search(texto):
            return f"Pergunta anterior (apenas referência): {anterior[1]}\nPergunta atual: {texto}"
        return texto
