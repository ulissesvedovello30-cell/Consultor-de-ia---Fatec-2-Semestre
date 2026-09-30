import re

import bcrypt

from config import CPF_SALT, RA_SALT


class Aluno:
    SEMESTRE_MAXIMO = 10

    def __init__(self, ra: str, nome: str, curso: str, cpf: str, semestre: int):
        self.__ra_hash = self.__gerar_hash_ra_validado(ra)
        self.__cpf_hash = self.__gerar_hash_cpf_validado(cpf)
        self._nome = None
        self._curso = None
        self._semestre = None
        
        self.nome = nome
        self.curso = curso
        self.semestre = semestre

    @staticmethod
    def __gerar_hash_ra_validado(ra: str) -> str:
        try:
            valor = int(ra)
        except (ValueError, TypeError) as e:
            raise ValueError(f"RA inválido: deve conter apenas números inteiros. ({e})") from e

        if valor < 0:
            raise ValueError("RA inválido: não pode ser negativo.")

        return Aluno.gerar_hash_ra(ra)

    @staticmethod
    def gerar_hash_ra(ra: str) -> str:
        valor = f"{ra}{RA_SALT}".encode("utf-8")
        hash_bytes = bcrypt.hashpw(valor, bcrypt.gensalt())
        return hash_bytes.decode("utf-8")

    @staticmethod
    def verificar_ra(ra: str, ra_hash_salvo: str) -> bool: 
        try:
            valor = f"{ra}{RA_SALT}".encode("utf-8")
            return bcrypt.checkpw(valor, ra_hash_salvo.encode("utf-8"))
        except (ValueError, TypeError, AttributeError) as e:
            raise ValueError(f"Erro ao verificar RA: {e}") from e

    @staticmethod
    def __gerar_hash_cpf_validado(cpf: str) -> str:
        try:
            digitos = re.sub(r"[.\-\s]", "", cpf)
        except TypeError as e:
            raise ValueError(f"CPF inválido: deve ser um texto. ({e})") from e

        if not (digitos.isascii() and digitos.isdigit()):
            raise ValueError("CPF inválido: deve conter apenas números.")
        if not Aluno.cpf_valido(digitos):
            raise ValueError("CPF inválido.")

        return Aluno.gerar_hash_cpf(digitos)

    @staticmethod
    def cpf_valido(digitos: str) -> bool:
        if len(digitos) != 11 or digitos == digitos[0] * 11:
            return False

        for tamanho in (9, 10):
            soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
            digito_verificador = (soma * 10 % 11) % 10
            if digito_verificador != int(digitos[tamanho]):
                return False

        return True

    @staticmethod
    def gerar_hash_cpf(cpf: str) -> str:
        valor = f"{cpf}{CPF_SALT}".encode("utf-8")
        hash_bytes = bcrypt.hashpw(valor, bcrypt.gensalt())
        return hash_bytes.decode("utf-8")

    @staticmethod
    def verificar_cpf(cpf: str, cpf_hash_salvo: str) -> bool:
        try:
            valor = f"{cpf}{CPF_SALT}".encode("utf-8")
            return bcrypt.checkpw(valor, cpf_hash_salvo.encode("utf-8"))
        except (ValueError, TypeError, AttributeError) as e:
            raise ValueError(f"Erro ao verificar CPF: {e}") from e

    @property
    def ra_hash(self) -> str:
        return self.__ra_hash

    @property
    def cpf_hash(self) -> str:
        return self.__cpf_hash

    @property
    def nome(self) -> str:
        return self._nome

    @nome.setter
    def nome(self, valor: str):
        try:
            valor_limpo = valor.strip()
        except AttributeError as e:
            raise ValueError(f"Nome inválido: deve ser um texto. ({e})") from e

        if not valor_limpo:
            raise ValueError("Nome não pode ser vazio.")
        if valor_limpo.lstrip("-").isdigit():
            raise ValueError("Nome não pode ser um número.")

        self._nome = valor_limpo

    @property
    def curso(self) -> str:
        return self._curso

    @curso.setter
    def curso(self, valor: str):
        try:
            valor_limpo = valor.strip()
        except AttributeError as e:
            raise ValueError(f"Curso inválido: deve ser um texto. ({e})") from e

        if not valor_limpo:
            raise ValueError("Curso não pode ser vazio.")

        self._curso = valor_limpo
    
    @property
    def semestre(self) -> int:
        return self._semestre
    
    @semestre.setter
    def semestre(self, semestre: int):
        try:
            valor = int(semestre)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Semestre inválido: deve ser um número. ({e})") from e

        if valor < 1 or valor > self.SEMESTRE_MAXIMO:
            raise ValueError(f"Semestre inválido: deve estar entre 1 e {self.SEMESTRE_MAXIMO}.")

        self._semestre = valor

        