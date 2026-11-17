"""Filtros temporais aplicados à data do evento, separados da descrição."""
import re
from aplicacao.servicos.extracao.calendario import MESES
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar


def filtrar_eventos(pergunta, eventos):
    """Respeite os meses e os anos explicitamente pedidos.

    Args:
        pergunta (str): Consulta normalizada.
        eventos (list): Fatos datados do calendário.

    Returns:
        list: Fatos cujas datas correspondem ao recorte solicitado.
    """
    meses = {normalizar(m) for m in MESES if re.search(r'\b' + normalizar(m) + r'\b', pergunta)}
    anos = set(re.findall(r'\b20\d{2}\b', pergunta))
    edicao = 'vestibular' in pergunta and not meses and bool(anos or re.search(r'semestre|ingress', pergunta))
    datas_anos = set() if edicao else anos
    return [t for t in eventos if data_compativel(t.texto, meses, datas_anos)
            and (not edicao or edicao_compativel(t.texto, pergunta, anos))]


def data_compativel(texto, meses, anos):
    """Compare filtros com a data, sem usar o ano citado no nome do vestibular.

    Args:
        texto (str): Fato datado extraído do PDF.
        meses (set): Meses solicitados.
        anos (set): Anos solicitados.

    Returns:
        bool: Indica se a data do evento atende aos filtros.
    """
    data = normalizar(texto.split(':', 1)[0])
    return (not meses or any(m in data for m in meses)) and (not anos or any(a in data for a in anos))


def edicao_compativel(texto, pergunta, anos):
    """Diferencie o ano do ingresso da data em que o exame acontece.

    Args:
        texto (str): Fato datado com a edição do vestibular na descrição.
        pergunta (str): Consulta normalizada.
        anos (set): Anos do ingresso explicitamente solicitados.

    Returns:
        bool: Indica correspondência da edição, mesmo quando o exame ocorre no ano anterior.
    """
    descricao = normalizar(texto.partition(':')[2])
    consulta = pergunta.replace('primeiro', '1').replace('segundo', '2')
    semestre = re.search(r'([12])[º°o]?\s+semestre', consulta)
    periodo = not semestre or bool(re.search(semestre[1] + r'[º°o]?\s+semestre', descricao))
    return periodo and (not anos or any(ano in descricao for ano in anos))
