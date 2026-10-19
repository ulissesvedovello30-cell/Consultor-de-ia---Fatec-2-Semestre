from dominio.aluno import Aluno

class CadastroAlunoService:
    def receber_dados(self, nome: str, sobrenome: str, ra: str, curso: str, semestre: int):
        cadastro = Aluno(nome=nome,sobrenome=sobrenome,ra=ra,curso=curso,semestre=semestre)
        return cadastro
