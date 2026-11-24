"""Correspondência das perguntas cadastradas na FAQ da secretaria."""
import re
from dataclasses import replace
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar, expandir_cursos
from aplicacao.servicos.recuperacao.consulta_textual import termos_consulta


def chave(pergunta):
    """Normalize pontuação e acentos sem alterar o significado da pergunta.

    Args:
        pergunta (str): Texto a comparar.

    Returns:
        str: Palavras normalizadas.
    """
    return ' '.join(re.findall(r'\w+', normalizar(pergunta)))


ASSUNTOS_RESERVADOS = frozenset((
    'catalogo', 'mensalidade', 'horario', 'modalidade',
    'periodicidade_vestibular', 'grade', 'duracao', 'nivel',
))


def assunto_do_bloco(trecho):
    """Extraia o marcador Assunto de um bloco da FAQ, ou vazio quando ausente."""
    achado = re.search(r'^Assunto:\s*(.+)$', trecho.texto, re.M)
    return achado.group(1).strip() if achado else ''


def eh_faq_customizada(trecho):
    """Indique se o trecho pertence à FAQ com um assunto livre adicionado pela secretaria."""
    if trecho.arquivo != 'FAQ_secretaria.txt':
        return False
    assunto = assunto_do_bloco(trecho)
    if assunto in ASSUNTOS_RESERVADOS:
        return False
    return 'Resposta:' in trecho.texto or (not assunto and 'Pergunta:' in trecho.texto)


def recortar_faq_customizada(trecho):
    """Remova marcadores internos Assunto/Pergunta/Resposta de blocos customizados da FAQ."""
    if trecho.arquivo != 'FAQ_secretaria.txt' or 'Resposta:' not in trecho.texto:
        return trecho
    resposta = trecho.texto.partition('Resposta:')[2].strip()
    return replace(trecho, texto=resposta) if resposta else trecho


def pergunta_do_trecho(trecho):
    """Extraia a pergunta de um bloco da FAQ fora dos assuntos já controlados por regras.

    Args:
        trecho: Trecho recuperado do acervo ativo.

    Returns:
        str: Pergunta normalizada ou string vazia para outros documentos.
    """
    if not eh_faq_customizada(trecho):
        return ''
    achado = re.search(r'^-?\s*Pergunta:\s*(.+)', trecho.texto, re.M)
    return chave(achado.group(1)) if achado else ''


def localizar(pergunta, trechos):
    """Localize correspondências exatas sem inserir respostas fora do acervo.

    Args:
        pergunta (str): Consulta do visitante.
        trechos (list): Versões ativas carregadas do repositório.

    Returns:
        list: Trechos coincidentes, com pontuação exata.
    """
    consulta = chave(pergunta)
    if not consulta:
        return []
    exatos = [recortar_faq_customizada(replace(t, similaridade=1.0))
              for t in trechos if pergunta_do_trecho(t) == consulta]
    return exatos or localizar_equivalentes(pergunta, trechos)


def localizar_equivalentes(pergunta, trechos):
    """Reconheça a mesma pergunta da FAQ após remover formas conversacionais.

    Args:
        pergunta (str): Consulta pública recebida.
        trechos (list): Trechos ativos, sem acrescentar respostas ao acervo.

    Returns:
        list: Blocos cuja pergunta cadastrada contém todos os assuntos consultados.
    """
    consulta = assunto_faq(pergunta)
    if not consulta:
        return []
    return [recortar_faq_customizada(replace(t, similaridade=1.0)) for t in trechos
            if (cadastrada := pergunta_do_trecho(t)) and consulta <= assunto_faq(cadastrada)]


def assunto_faq(pergunta):
    """Compare assuntos da FAQ geral sem usar as siglas dos cursos como ruído.

    Args:
        pergunta (str): Pergunta cadastrada ou recebida do visitante.

    Returns:
        set[str]: Assuntos normalizados com a mesma regra da busca textual.
    """
    return termos_consulta(expandir_cursos(normalizar(pergunta)), {'ia', 'esg'})


def priorizar(trechos):
    """Use a FAQ geral quando ela for a evidência mais próxima da pergunta.

    Args:
        trechos (list): Evidências já aprovadas pelo limiar de similaridade.

    Returns:
        list: FAQ geral ou os trechos originais para a consulta acadêmica.
    """
    if any(t.grupo_resposta.startswith('consulta:') for t in trechos):
        return trechos
    try:
        (True,).index(trechos[0].arquivo == 'FAQ_secretaria.txt')
    except (IndexError, ValueError):
        return trechos
    return [t for t in trechos if t.arquivo == 'FAQ_secretaria.txt']
