import re
import unicodedata


def normalizar(texto):
    """Retorne texto sem acentos e em minúsculas para comparação de metadados."""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).casefold())
                   if not unicodedata.combining(c))


def mencionados(pergunta, valores):
    """Retorne os valores de metadados mencionados como palavras na pergunta."""
    texto = normalizar(pergunta)
    return {v for v in valores if re.search(r'(?<!\w)' + re.escape(normalizar(v)) + r'(?!\w)', texto)}


def delimitar(pergunta, trechos):
    """Filtre trechos por metadados explícitos e retorne campos ambíguos pendentes."""
    pendentes = []
    for campo in ('curso', 'periodo', 'ano'):
        valores = {getattr(t, campo) for t in trechos if getattr(t, campo)}
        escolhidos = mencionados(pergunta, valores)
        if escolhidos:
            trechos = [t for t in trechos if not getattr(t, campo) or getattr(t, campo) in escolhidos]
        elif len(valores) > 1:
            pendentes.append(campo + ' (' + ', '.join(map(str, sorted(valores))) + ')')
    return trechos, pendentes
