from dominio.mensageiro import Mensageiro
from infra.banco_de_dados import BancoDeDados
from servicos.interpretador_llm import InterpretadorLLM

class Chatbot:
    def __init__(self, banco_de_dados: BancoDeDados, interpretador: InterpretadorLLM, telegram: TelegramGateway):
        self.banco_de_dados = banco_de_dados
        self.interpretador = interpretador
        self.telegram = telegram
        self.sessoes = {}  # dict chat_id -> Sessao

    def processar_mensagem(self, chat_id: str, texto: str):
        pass
