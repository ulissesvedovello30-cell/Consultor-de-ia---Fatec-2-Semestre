class IntentDetectada:
    def __init__(self, tipo_intent: str, parametros: dict, confianca: float):
        self.__tipo_intent = tipo_intent
        self.__parametros = parametros
        self.__confianca = confianca

    @property
    def tipo_intent(self) -> str:
        return self.__tipo_intent

    @property
    def parametros(self) -> dict:
        return self.__parametros

    @property
    def confianca(self) -> float:
        return self.__confianca
