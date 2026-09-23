from datetime import datetime, timedelta

from dominio.aluno import Aluno


class Sessao:
    TIMEOUT_MINUTOS = 30

    def __init__(self, chat_id: str):
        self.__chat_id = chat_id
        self.__aluno = None
        self.__verificado = False
        self.__ultima_atividade = datetime.now()

    @property
    def chat_id(self) -> str:
        return self.__chat_id

    @property
    def aluno(self) -> Aluno:
        return self.__aluno

    @property
    def verificado(self) -> bool:
        return self.__verificado

    def verificar(self, aluno: Aluno):
        self.__aluno = aluno
        self.__verificado = True
        self.registrar_atividade()

    def registrar_atividade(self):
        self.__ultima_atividade = datetime.now()

    def esta_expirada(self) -> bool:
        tempo_decorrido = datetime.now() - self.__ultima_atividade
        return tempo_decorrido > timedelta(minutes=self.TIMEOUT_MINUTOS)
