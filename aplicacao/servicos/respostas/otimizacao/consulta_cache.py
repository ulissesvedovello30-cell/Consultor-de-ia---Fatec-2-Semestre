"""Equivalência conservadora de perguntas sobre grupos documentais estruturados."""
from aplicacao.servicos.recuperacao.consulta_textual import termos
from aplicacao.servicos.recuperacao.filtros_acervo import expandir_cursos, normalizar
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta

COMUNS = {'caso', 'cada', 'um', 'dois', 'ambos', 'todos', 'igual', 'entao', 'assunto'}
PERMITIDAS = {
    'duracao': COMUNS | {'duracao', 'anos', 'semestres', 'minimo', 'maximo', 'prazo', 'integralizacao', 'conclusao'},
    'modalidade': COMUNS | {'modalidade', 'presencial'},
    'recesso': COMUNS | {'recesso', 'inicio', 'termino', 'aula', 'apos', 'depois'},
    'faq:mensalidade': COMUNS | {'mensalidade', 'mensalidades', 'gratuito', 'gratuitos', 'gratis', 'custo', 'custa', 'valor', 'preco', 'estudar'},
    'faq:horario': COMUNS | {'horario', 'horas', 'aula', 'inicio', 'termino', 'turno'},
    'faq:modalidade': COMUNS | {'modalidade', 'presencial', 'ead', 'online', 'distancia', 'aula', 'assincrona', 'assincronas', 'nao'},
    'faq:grade': COMUNS | {'grade', 'curricular', 'acesso', 'acessar', 'link', 'consultar', 'ver', 'vejo', 'disciplina'},
    'faq:nivel': COMUNS | {'nivel', 'superior', 'superiores', 'tecnico', 'tecnicos', 'tecnologo'},
}


def pergunta_canonica(pergunta, trechos):
    """Reutilize a seleção de uma variação apenas quando não houver qualificadores novos.

    Args:
        pergunta (str): Pergunta original já aprovada pela política de entrada.
        trechos (list): Grupo de evidências recuperadas para essa pergunta.

    Returns:
        str: Intenção canônica ou a própria pergunta quando sua equivalência não for reconhecida.
    """
    tipos = {t.tipo_info for t in trechos}
    tipo = 'recesso' if tipos and tipos <= {'recesso', 'retorno_aulas'} else next(iter(tipos), '')
    palavras = termos(expandir_cursos(preparar_consulta(pergunta))) - {normalizar(t.curso) for t in trechos if t.curso}
    palavras -= {p for p in palavras if p.isdecimal() and any(p in t.texto for t in trechos)}
    if len(tipos) == 1 or tipo == 'recesso':
        if tipo in PERMITIDAS and not palavras - PERMITIDAS[tipo]:
            return 'grupo documental: ' + tipo
    return pergunta
