from dominio.aluno import Aluno
from infra.banco_de_dados import BancoDeDados

class CadastroAlunoService:

    def __init__(self, banco_de_dados: BancoDeDados):
        self.banco_de_dados = banco_de_dados

    def cadastrar(self, nome: str, ra: str, cpf: str, curso: str, semestre: int) -> Aluno:
        cadastro = Aluno(nome=nome,ra=ra,cpf=cpf,curso=curso,semestre=semestre)
        return cadastro

    def dados_repetidos(self, cpf):
        self.banco_de_dados.executar_query()
        for cpf in self:
            if cpf == cpf:
                return True
            return False