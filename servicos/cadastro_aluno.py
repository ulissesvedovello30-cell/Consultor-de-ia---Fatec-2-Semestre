from dominio.aluno import Aluno

class CadastroAlunoService:
    def receber_dados(self, nome: str, ra: str, cpf: str, curso: str, semestre: int):
        cadastro = Aluno(nome=nome,ra=ra,cpf=cpf,curso=curso,semestre=semestre)
        return cadastro