class RespostaChatbot:
    def __init__(self, texto: str, sucesso: bool, score_qualidade: float):
        self.__texto = texto
        self.__sucesso = sucesso
        self.__score_qualidade = score_qualidade

    @property
    def texto(self) -> str:
        return self.__texto

    @property
    def sucesso(self) -> bool:
        return self.__sucesso

    @property
    def score_qualidade(self) -> float:
        return self.__score_qualidade
