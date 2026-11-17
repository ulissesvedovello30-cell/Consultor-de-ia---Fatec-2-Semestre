"""Correspondência das perguntas cadastradas na FAQ da secretaria."""
import re
from dataclasses import replace
from servicos.filtros_acervo import normalizar, expandir_cursos
from servicos.consulta_textual import termos_consulta


def chave(pergunta):
    """Normalize pontuação e acentos sem alterar o significado da pergunta.

    Args:
        pergunta (str): Texto a comparar.

    Returns:
        str: Palavras normalizadas.
    """
    return ' '.join(re.findall(r'\w+', normalizar(pergunta)))


def pergunta_do_trecho(trecho):
    """Extraia a pergunta de um bloco completo da FAQ.

    Args:
        trecho: Trecho recuperado do acervo ativo.

    Returns:
        str: Pergunta normalizada ou string vazia para outros documentos.
    """
    try:
        (True,).index(trecho.arquivo == 'FAQ_secretaria.txt')
        texto = re.search(r'^-?\s*Pergunta: (.+)', trecho.texto).group(1)
    except (ValueError, AttributeError):
        return ''
    return chave(texto)


def localizar(pergunta, trechos):
    """Localize correspondências exatas sem inserir respostas fora do acervo.

    Args:
        pergunta (str): Consulta do visitante.
        trechos (list): Versões ativas carregadas do repositório.

    Returns:
        list: Trechos coincidentes, com pontuação exata.
    """
    consulta = chave(pergunta)
    try:
        (True,).index(bool(consulta))
    except ValueError:
        return []
    exatos = [replace(t, similaridade=1.0) for t in trechos if pergunta_do_trecho(t) == consulta]
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
    return [replace(t, similaridade=1.0) for t in trechos
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
    try:
        (True,).index(trechos[0].arquivo == 'FAQ_secretaria.txt')
    except (IndexError, ValueError):
        return trechos
    return [t for t in trechos if t.arquivo == 'FAQ_secretaria.txt']
