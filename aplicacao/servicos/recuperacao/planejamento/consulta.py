"""Reconhecimento de assuntos e referências sem usar a frase inteira como filtro."""
import re
from aplicacao.servicos.recuperacao.consulta_textual import termos
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta
from aplicacao.servicos.recuperacao.perguntas.assuntos import assuntos_frequentes


def assunto_curso(pergunta):
    """Reconheça duração e modalidade como propriedades do curso.

    Args:
        pergunta (str): Pergunta recebida, com linguagem conversacional.

    Returns:
        str: Propriedade reconhecida, ou vazio para a busca geral.
    """
    texto = preparar_consulta(pergunta)
    palavras = termos(texto)
    if re.search(r'estagio|hora.?aula|prova|vestibular|recesso|ferias|matricula|inscri|transferencia|biblioteca|secretaria', texto):
        return ''
    if 'duracao' in palavras or re.search(r'quantos (?:anos|semestres)|(?:demora|leva).*curso|prazo.*(?:conclusao|integralizacao)', texto):
        return 'duracao'
    assuntos = assuntos_frequentes(texto)
    return next(iter(assuntos)) if len(assuntos) == 1 else ''


def consulta_coletiva(pergunta, cursos=None):
    """Identifique pedidos que abrangem mais de um curso.

    Args:
        pergunta (str): Pergunta original ou resolvida pelo contexto da conversa.
        cursos (set[str] | None): Cursos disponíveis no conjunto consultado.

    Returns:
        bool: Indica uma consulta coletiva explícita.
    """
    from aplicacao.servicos.recuperacao.filtros_acervo import mencionados
    conhecidos = set(cursos or ()) | {'IA', 'ESG'}
    return bool(pedido_coletivo(pergunta) or (assunto_curso(pergunta) and not mencionados(pergunta, conhecidos)))


def pedido_coletivo(pergunta):
    """Reconheça um pedido explícito por vários cursos antes de herdar o contexto.

    Args:
        pergunta (str): Pergunta atual do visitante.

    Returns:
        bool: Indica plural ou quantificador coletivo escrito na pergunta.
    """
    texto = preparar_consulta(pergunta)
    return bool(re.search(r'\b(?:cursos|graduacoes|tecnologos|ambos|dois|todos)\b|cada\s+(?:curso|graduacao|tecnologo|um)', texto))
