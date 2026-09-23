class Professor:
    def __init__(self, nome: str, codigo: str):
        self.__nome = nome
        self.__codigo = codigo

    @property
    def nome(self) -> str:
        return self.__nome

    @property
    def codigo(self) -> str:
        return self.__codigo
