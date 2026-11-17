"""Preparação de consulta textual, sem interpretar comandos do usuário."""
import re
from servicos.filtros_acervo import normalizar

IGNORADAS = frozenset(('a o as os de da do das dos e em no na nos nas um uma uns umas para por com '
    'que qual quais como quanto quantos quantas quando onde eu meu minha seus suas seu sua '
    'sobre saber gostaria quero preciso voces voce me ao aos pela pelo pelas pelos se ser sao '
    'tem ter esta este isso esse essa dessa desse daqui fatec faculdade curso cursos '
    'estao pode podem poderia poderiam informar informe explicar explica diga dizer '
    'acontece acontecem funciona funcionam cobra cobram favor porfavor').split())

FORMAS = {
    'duracao': ('duracao', 'duracoes', 'dura', 'duram'),
    'horario': ('horario', 'horarios'),
    'disciplina': ('disciplina', 'disciplinas', 'materia', 'materias', 'componente', 'componentes'),
    'aula': ('aula', 'aulas'),
    'oferta': ('oferta', 'ofertas', 'oferece', 'oferecem', 'oferecido', 'oferecidos', 'oferecida', 'oferecidas'),
    'objetivo': ('objetivo', 'objetivos'),
    'requisito': ('requisito', 'requisitos'),
    'acesso': ('acesso', 'acessos', 'ingresso', 'ingressar', 'entrar'),
    'evento': ('evento', 'eventos'),
    'prova': ('prova', 'provas'),
    'inscricao': ('inscricao', 'inscricoes'),
    'presencial': ('presencial', 'presenciais'),
}
EQUIVALENTES = {forma: chave for chave, formas in FORMAS.items() for forma in formas}


def termos(texto):
    """Normalize acentos e descarte palavras funcionais de uma pergunta.

    Args:
        texto (str): Pergunta ou trecho documental.

    Returns:
        set[str]: Termos alfanuméricos; nunca contém operadores FTS.
    """
    palavras = {t for t in re.findall(r'[a-z0-9]+', normalizar(texto))
                if t not in IGNORADAS and len(t) > 1}
    return {equivalente(p) for p in palavras}


def expressao(palavras, operador='OR'):
    """Forme uma busca OR somente com palavras escapadas.

    Args:
        palavras (set[str]): Palavras já normalizadas.
        operador (str): União OR ou interseção AND entre os grupos de termos.

    Returns:
        str: Expressão FTS5 sem fragmentos de SQL do usuário.
    """
    if operador not in ('OR', 'AND'):
        raise ValueError('Operador de busca inválido.')
    grupos = [grupo_fts(palavra) for palavra in sorted(palavras)[:40]]
    return (' ' + operador + ' ').join(grupos)


def cobertura(palavras, texto):
    """Calcule a fração de termos presentes; não representa probabilidade de verdade."""
    return len(palavras & termos(texto)) / max(1, len(palavras))


def equivalente(palavra):
    """Reconheça apenas flexões e equivalentes institucionais explícitos."""
    return EQUIVALENTES.get(palavra, palavra)


def grupo_fts(palavra):
    """Consulte no índice original as mesmas variantes usadas na pontuação.

    Args:
        palavra (str): Termo normalizado sem operadores de consulta.

    Returns:
        str: Grupo FTS com alternativas literais protegidas.
    """
    formas = FORMAS.get(palavra, (palavra,))
    formas = [p for p in formas if re.fullmatch('[a-z0-9]+', p)]
    return '(' + ' OR '.join('"' + p + '"' for p in formas) + ')'


def termos_consulta(pergunta, ignoradas=()):
    """Retire termos genéricos somente quando houver um assunto mais específico.

    Args:
        pergunta (str): Pergunta normalizada e com os nomes dos cursos expandidos.
        ignoradas (Iterable[str]): Metadados já utilizados para filtrar os documentos.

    Returns:
        set[str]: Termos usados de forma consistente na busca e na pontuação.
    """
    palavras = termos(pergunta) - set(ignoradas)
    especificas = palavras - {'oferta', 'aula'}
    if especificas:
        return especificas
    if not palavras and re.search(r'\bcursos?\b', normalizar(pergunta)):
        return {'oferta'}
    return palavras
