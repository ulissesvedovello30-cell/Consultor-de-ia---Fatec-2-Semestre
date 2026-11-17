"""Formatação de campos documentais sem criar números, datas ou respostas livres."""
import re
from aplicacao.servicos.respostas.apresentacao.vestibular import texto_inscricao


def texto_campo(frase, tipo):
    """Apresente prazos e eventos com os rótulos correspondentes.

    Args:
        frase (str): Passagem que já passou pela validação literal.
        tipo (str): Papel atribuído pela recuperação estruturada.

    Returns:
        str: Campo legível, ou a passagem original quando o formato não for conhecido.
    """
    if tipo == 'catalogo':
        return 'Tecnologia em ' + frase
    if tipo == 'inscricao':
        return texto_inscricao(frase)
    if tipo == 'duracao':
        return texto_duracao(frase)
    if tipo == 'modalidade':
        return 'Modalidade: ' + re.sub(r'^-?\s*Modalidade\s+', '', frase, flags=re.I).rstrip('.') + '.'
    return texto_evento(frase, tipo)


def texto_evento(frase, tipo):
    """Resuma datas apenas quando a descrição não trouxer uma ressalva adicional.

    Args:
        frase (str): Fato datado e validado.
        tipo (str): Papel conhecido do evento.

    Returns:
        str: Data rotulada ou passagem original com todas as suas condições.
    """
    rotulos = {'recesso': ('Recesso oficial', r'per[ií]odo de recesso'),
               'retorno_aulas': ('Retorno às aulas', r'in[ií]cio das aulas do [12]º semestre letivo de 20\d{2}')}
    try:
        rotulo, padrao = rotulos[tipo]
    except KeyError:
        return frase
    data, _, descricao = [parte.strip() for parte in frase.lstrip('- ').partition(':')]
    if re.fullmatch(padrao, descricao.strip(), re.I) is None:
        return frase
    return rotulo + ': ' + data[:1].lower() + data[1:] + '.'


def texto_duracao(frase):
    """Separe duração mínima e prazo máximo sem calcular valores novos.

    Args:
        frase (str): Campo original de integralização de um PPC.

    Returns:
        str: Valores extraídos e rotulados, ou a passagem original se o padrão divergir.
    """
    valores = re.search(r'M[ií]nimo de\s+(.*?)\s*M[aá]ximo de\s+(.+)', frase, re.S | re.I)
    if valores is None:
        return frase
    minimo, maximo = [limpar_valor(v) for v in valores.groups()]
    return f'Duração mínima: {minimo}.\nPrazo máximo de integralização: {maximo}.'


def limpar_valor(texto):
    """Ajuste espaços e zeros à esquerda exclusivamente no campo de duração.

    Args:
        texto (str): Valor extraído literalmente do campo do PPC.

    Returns:
        str: Mesmo valor com apresentação numérica regular.
    """
    return re.sub(r'\b0+(\d+)\b', r'\1', ' '.join(texto.split())).rstrip('.;')
