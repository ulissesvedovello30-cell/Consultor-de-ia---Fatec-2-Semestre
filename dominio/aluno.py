import bcrypt

from config import RA_SALT


class Aluno:
    def __init__(self, ra: str, nome: str, curso: str):
        self.__ra_hash = self.__gerar_hash_ra_validado(ra)
        self._nome = None
        self._curso = None

        self.nome = nome
        self.curso = curso

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

    @property
    def ra_hash(self) -> str:
        return self.__ra_hash

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

        