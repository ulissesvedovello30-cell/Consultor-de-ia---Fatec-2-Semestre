import hashlib
import hmac

from config import RA_SALT


class Aluno:
    SEMESTRE_MAXIMO = 10
    RA_TAMANHO_MAXIMO = 15  # igual à coluna RA do banco original (varchar(15)); também limita o que é hasheado
    lista_caracteres_permitidos = {"-", ".", "’", "'", " "}

    def __init__(self, ra: str, nome: str, sobrenome: str, curso: str, semestre: int):
        self.__ra_hash = Aluno.gerar_hash_ra(ra)
        self._nome = None
        self._sobrenome = None
        self._curso = None
        self._semestre = None
        
        self.nome = nome
        self.sobrenome = sobrenome
        self.curso = curso
        self.semestre = semestre

    @staticmethod
    def normalizar_ra(ra: str) -> str:
        """Valida o RA e devolve na forma canônica (sem espaços nas pontas).

        O hash só é igual para o mesmo aluno se o texto que entra nele for sempre o
        mesmo: sem isso, "123" e " 123" virariam dois alunos diferentes.
        """
        try:
            valor = ra.strip()
        except AttributeError as e:
            raise ValueError(f"RA inválido: deve ser um texto. ({e})") from e

        if not (valor.isascii() and valor.isdigit()):
            raise ValueError("RA inválido: deve conter apenas números.")
        if len(valor) > Aluno.RA_TAMANHO_MAXIMO:
            raise ValueError(f"RA inválido: no máximo {Aluno.RA_TAMANHO_MAXIMO} dígitos.")

        return valor

    @staticmethod
    def gerar_hash_ra(ra: str) -> str:
        """HMAC-SHA256 do RA com a chave secreta (RA_SALT).

        Determinístico: o mesmo RA sempre dá o mesmo hash, então o banco acha o aluno
        com `WHERE ra_hash = %s` e o UNIQUE barra RA repetido. O bcrypt não permite isso.
        """
        if not RA_SALT:
            raise RuntimeError("RA_SALT não está configurado no .env.")
        return hmac.new(
            RA_SALT.encode("utf-8"), Aluno.normalizar_ra(ra).encode("ascii"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verificar_ra(ra: str, ra_hash_salvo: str) -> bool:
        try:
            # compare_digest leva o mesmo tempo acertando ou errando: não vaza, pelo
            # tempo de resposta, quantos caracteres do hash batem.
            return hmac.compare_digest(Aluno.gerar_hash_ra(ra), ra_hash_salvo)
        except TypeError as e:
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
    def sobrenome(self) -> str:
        return self._sobrenome

    @sobrenome.setter
    def sobrenome(self, valor: str):
        try:
            valor_limpo = valor.strip()
        except AttributeError as e:
            raise ValueError(f"Sobrenome inválido: deve ser um texto. ({e})") from e
        if not any(c.isalpha() for c in valor_limpo):
            raise ValueError("Sobrenome precisa ter pelo menos uma letra.")
        if valor_limpo.startswith(("-",".")):
            raise ValueError("Sobrenome não pode começar com traço ou ponto")
        carac_invalidos = sorted({i for i in valor_limpo.lower() if not (i.isalpha() or i in self.lista_caracteres_permitidos)})
        if carac_invalidos:
            raise ValueError("Caractere inválido")
        if not valor_limpo:
            raise ValueError("Sobrenome não pode ser vazio.")
        if valor_limpo.lstrip("-").isdigit():
            raise ValueError("Sobrenome não pode ser um número.")

        self._sobrenome = valor_limpo


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

        