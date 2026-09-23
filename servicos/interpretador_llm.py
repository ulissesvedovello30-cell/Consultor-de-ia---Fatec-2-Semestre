from dominio.intent_detectada import IntentDetectada


class InterpretadorLLM:
    def __init__(self, api_key: str, modelo: str, temperatura: float = 0.2):
        self.__api_key = api_key
        self.modelo = modelo
        self.temperatura = temperatura

    def interpretar_mensagem(self, texto: str) -> IntentDetectada:
        pass
