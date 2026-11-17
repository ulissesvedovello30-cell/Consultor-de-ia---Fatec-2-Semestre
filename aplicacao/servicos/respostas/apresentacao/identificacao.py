"""Identificação do curso de cada afirmação, separada da lista de fontes."""
from aplicacao.servicos.respostas.apresentacao.texto import texto_campo


def apresentar_afirmacao(frase, ids, usados):
    """Acrescente o nome do curso e formate somente campos reconhecidos.

    Args:
        frase (str): Afirmação já verificada contra as fontes.
        ids (list): Referências internas aprovadas pelo validador.
        usados (list): Evidências do contexto da geração.

    Returns:
        str: Resposta com identificação acadêmica, sem nomes de arquivos ou citações.
    """
    fontes = [usados[i - 1] for i in ids]
    nomes = list(dict.fromkeys(t.nome_curso or t.curso for t in fontes if t.curso))
    tipos = {t.tipo_info for t in fontes}
    texto = texto_campo(frase, next(iter(tipos))) if len(tipos) == 1 else frase
    if not nomes or frase.strip() in nomes:
        return texto
    return ' / '.join(nomes) + ':\n' + texto
