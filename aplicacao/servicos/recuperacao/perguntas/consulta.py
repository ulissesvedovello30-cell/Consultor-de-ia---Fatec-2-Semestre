"""Consulta da FAQ com filtros por assunto e curso, sem respostas no código."""
import re
from aplicacao.servicos.recuperacao.filtros_acervo import mencionados
from aplicacao.servicos.recuperacao.perguntas.assuntos import assuntos_frequentes
from aplicacao.servicos.recuperacao.perguntas.evidencias import ficha_faq
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta


TERMOS_GENERICOS_CURSO = frozenset((
    'aula', 'aulas', 'curso', 'cursos', 'ensino', 'tecnologia', 'tecnologo', 'tecnologos',
    'graduacao', 'graduacoes', 'inscricao', 'inscricoes', 'disciplina', 'disciplinas',
    'materia', 'materias', 'faculdade', 'fatec', 'semestre', 'semestres', 'ano', 'anos',
    'manha', 'tarde', 'noite', 'noturno', 'matutino', 'vespertino', 'integral',
))


def curso_desconhecido(pergunta, cursos=None):
    """Evite responder sobre cursos cadastrados quando outro curso foi solicitado.

    Args:
        pergunta (str): Consulta recebida.
        cursos (set[str] | None): Cursos presentes no acervo ativo.

    Returns:
        bool: Indica uma referência explícita a curso sem identificação conhecida.
    """
    texto = preparar_consulta(pergunta)
    conhecidos = set(cursos or ()) | {'IA', 'ESG'}
    if mencionados(texto, conhecidos):
        return False
    explicito = re.search(r'\bcurso (?:de|em) (\w+)', texto)
    if explicito and explicito[1] not in TERMOS_GENERICOS_CURSO and not re.fullmatch(r'20\d{2}', explicito[1]):
        return True
    alvo = re.search(r'(?:mensalidade|horario|duracao|grade|curso|graduacao).*\b(?:de|em)\s+(\w+)\s*[?.!]*$', texto)
    if alvo and alvo[1] not in TERMOS_GENERICOS_CURSO and not re.fullmatch(r'20\d{2}', alvo[1]):
        return True
    return False


def buscar_frequentes(pergunta, textos, k):
    """Busque propriedades conhecidas mesmo sem o usuário informar os cursos.

    Args:
        pergunta (str): Consulta original ou resolvida pela conversa.
        textos (list): Evidências ativas, incluindo a FAQ quando publicada.
        k (int): Limite de candidatos.

    Returns:
        list | None: Respostas documentadas ou None para continuar a recuperação.
    """
    cursos_ativos = {t.curso for t in textos if t.curso} | {'IA', 'ESG'}
    if curso_desconhecido(pergunta, cursos_ativos):
        return None
    assuntos = assuntos_frequentes(pergunta)
    cursos = mencionados(pergunta, cursos_ativos)
    fichas = [ficha_faq(t, assuntos, cursos) for t in textos]
    return [t for t in fichas if t is not None][:k] or None
