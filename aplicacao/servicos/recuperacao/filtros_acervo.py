import re
import unicodedata


def normalizar(texto):
    """Retorne texto sem acentos e em minúsculas para comparação de metadados."""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).casefold())
                   if not unicodedata.combining(c))


def forma_curso(valor):
    """Normalize sigla ou nome completo do curso para a mesma chave de comparação."""
    return expandir_cursos(normalizar(valor))


def mencionados(pergunta, valores):
    """Retorne os valores de metadados mencionados na pergunta, inclusive nomes completos equivalentes."""
    from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta
    texto = expandir_cursos(preparar_consulta(pergunta))
    return {v for v in valores if any(
        re.search(r'(?<!\w)' + re.escape(forma) + r'(?!\w)', texto)
        for forma in {normalizar(v), forma_curso(v)} if forma
    )}


def delimitar(pergunta, trechos):
    """Filtre trechos por metadados explícitos e retorne campos ambíguos pendentes."""
    from aplicacao.servicos.recuperacao.planejamento.consulta import consulta_coletiva
    pendentes = []
    for campo in ('curso', 'periodo', 'ano'):
        valores = {getattr(t, campo) for t in trechos if getattr(t, campo)}
        escolhidos = mencionados(pergunta, valores)
        if escolhidos:
            trechos = [t for t in trechos if not getattr(t, campo) or getattr(t, campo) in escolhidos]
        else:
            distintos = {forma_curso(v) for v in valores} if campo == 'curso' else valores
            if len(distintos) > 1 and not (campo == 'curso' and consulta_coletiva(pergunta, valores)):
                pendentes.append(campo + ' (' + ', '.join(map(str, sorted(valores))) + ')')
    return trechos, pendentes


def expandir_cursos(texto):
    """Reconheça os nomes completos dos cursos usados nos metadados.

    Args:
        texto (str): Pergunta previamente normalizada.

    Returns:
        str: Consulta com siglas equivalentes para delimitação do curso.
    """
    texto = re.sub(r'\bi\s*\.\s*a\s*\.?', 'ia', texto)
    aliases = {'inteligencia artificial': 'ia',
               'gestao da sustentabilidade ambiental, social e governanca corporativa': 'esg',
               'gestao da sustentabilidade ambiental social e governanca corporativa': 'esg',
               'gestao da sustentabilidade': 'esg'}
    for nome, sigla in aliases.items():
        texto = texto.replace(nome, sigla)
    return texto
