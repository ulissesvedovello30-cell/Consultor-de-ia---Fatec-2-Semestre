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


def resolver_referencia(atual, anterior):
    """Complete somente o assunto ou o curso que faltar na pergunta atual.

    Args:
        atual (str): Pergunta original do visitante.
        anterior (str): Última pergunta respondida na mesma sessão.

    Returns:
        str | None: Pergunta resolvida, ou None para o contexto genérico existente.
    """
    assunto = assunto_curso(atual)
    cursos = mencionados(atual, {'IA', 'ESG'})
    if assunto and (cursos or pedido_coletivo(atual)):
        return atual
    if assunto:
        return herdar_curso(atual, anterior)
    previo = assunto_curso(anterior)
    palavras = termos(preparar_consulta(atual)) - {c.lower() for c in cursos} - REFERENCIAS
    return f'Assunto: {ROTULOS[previo]}. {atual}' if previo and cursos and not palavras else None


def herdar_curso(atual, anterior):
    """Use um curso anterior somente em uma pergunta de propriedade sem curso explícito.

    Args:
        atual (str): Consulta que já tem assunto reconhecido.
        anterior (str): Última consulta resolvida da mesma conversa.

    Returns:
        str: Consulta enriquecida ou original quando houver ambiguidade.
    """
    cursos = mencionados(anterior, {'IA', 'ESG'})
    desconhecido = re.search(r'curso de\s+\w+', normalizar(atual))
    if len(cursos) == 1 and not pedido_coletivo(atual) and not desconhecido:
        return 'Curso: ' + next(iter(cursos)) + '. ' + atual
    return atual
