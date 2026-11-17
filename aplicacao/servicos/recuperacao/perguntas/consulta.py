"""Consulta da FAQ com filtros por assunto e curso, sem respostas no código."""
import re
from aplicacao.servicos.recuperacao.filtros_acervo import mencionados
from aplicacao.servicos.recuperacao.perguntas.assuntos import assuntos_frequentes
from aplicacao.servicos.recuperacao.perguntas.evidencias import ficha_faq
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta


def curso_desconhecido(pergunta):
    """Evite responder sobre IA ou ESG quando outro curso foi solicitado.

    Args:
        pergunta (str): Consulta recebida.

    Returns:
        bool: Indica uma referência explícita a curso sem identificação conhecida.
    """
    texto = preparar_consulta(pergunta)
    if mencionados(texto, {'IA', 'ESG'}):
        return False
    alvo = re.search(r'(?:mensalidade|horario|duracao|grade|curso|graduacao).*\b(?:de|em)\s+(\w+)\s*[?.!]*$', texto)
    return bool(re.search(r'curso (?:de|em) \w+', texto) or
                (alvo and alvo[1] not in {'aula', 'aulas', 'curso', 'cursos', 'ensino', 'tecnologia',
                                         'inscricao', 'inscricoes', 'disciplinas', 'faculdade'}))


def buscar_frequentes(pergunta, textos, k):
    """Busque propriedades conhecidas mesmo sem o usuário informar os cursos.

    Args:
        pergunta (str): Consulta original ou resolvida pela conversa.
        textos (list): Evidências ativas, incluindo a FAQ quando publicada.
        k (int): Limite de candidatos.

    Returns:
        list | None: Respostas documentadas ou None para continuar a recuperação.
    """
    if curso_desconhecido(pergunta):
        return None
    assuntos = assuntos_frequentes(pergunta)
    cursos = mencionados(pergunta, {'IA', 'ESG'})
    fichas = [ficha_faq(t, assuntos, cursos) for t in textos]
    return [t for t in fichas if t is not None][:k] or None
