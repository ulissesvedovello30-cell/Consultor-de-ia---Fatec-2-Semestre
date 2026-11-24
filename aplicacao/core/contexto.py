"""Resolva referências curtas sem misturar os cursos de duas perguntas."""
import re
from aplicacao.servicos.recuperacao.consulta_textual import termos
from aplicacao.servicos.recuperacao.filtros_acervo import mencionados, normalizar
from aplicacao.servicos.recuperacao.planejamento.consulta import assunto_curso, pedido_coletivo
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta

ROTULOS = {'duracao': 'duração do curso', 'modalidade': 'modalidade do curso',
           'horario': 'horário do curso', 'mensalidade': 'mensalidade do curso',
           'grade': 'grade curricular do curso', 'nivel': 'nível do curso'}
REFERENCIAS = {'caso', 'cada', 'ele', 'ela', 'dele', 'dela', 'esse', 'essa', 'isso', 'tambem'}
ANAF_DEMONSTRATIVO = re.compile(r'\b(isso|disso|esse|essa|desse|dessa|nele|nela)\b', re.I)


def resolver_referencia(atual, anterior, cursos_conhecidos=None):
    """Complete somente o assunto ou o curso que faltar na pergunta atual.

    Args:
        atual (str): Pergunta original do visitante.
        anterior (str): Última pergunta respondida na mesma sessão.
        cursos_conhecidos (Iterable[str] | None): Cursos ativos no acervo.

    Returns:
        str | None: Pergunta resolvida, ou None para o contexto genérico existente.
    """
    conhecidos = set(cursos_conhecidos or ()) | {'IA', 'ESG'}
    assunto = assunto_curso(atual)
    cursos = mencionados(atual, conhecidos)
    if assunto and (cursos or pedido_coletivo(atual)):
        return atual
    if assunto:
        if ANAF_DEMONSTRATIVO.search(atual) and not mencionados(anterior, conhecidos):
            return None
        return herdar_curso(atual, anterior, conhecidos)
    previo = assunto_curso(anterior)
    palavras = termos(preparar_consulta(atual)) - {c.lower() for c in cursos} - REFERENCIAS
    return f'Assunto: {ROTULOS[previo]}. {atual}' if previo in ROTULOS and cursos and not palavras else None


def herdar_curso(atual, anterior, cursos_conhecidos=None):
    """Use um curso anterior somente em uma pergunta de propriedade sem curso explícito.

    Args:
        atual (str): Consulta que já tem assunto reconhecido.
        anterior (str): Última consulta resolvida da mesma conversa.
        cursos_conhecidos (set[str] | None): Cursos disponíveis no acervo.

    Returns:
        str: Consulta enriquecida ou original quando houver ambiguidade.
    """
    from aplicacao.servicos.recuperacao.perguntas.consulta import curso_desconhecido
    conhecidos = set(cursos_conhecidos or ()) | {'IA', 'ESG'}
    cursos = mencionados(anterior, conhecidos)
    if len(cursos) == 1 and not pedido_coletivo(atual) and not curso_desconhecido(atual, conhecidos):
        return 'Curso: ' + next(iter(cursos)) + '. ' + atual
    return atual
