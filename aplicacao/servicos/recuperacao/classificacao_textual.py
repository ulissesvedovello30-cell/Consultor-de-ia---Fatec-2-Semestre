"""Ordenação de evidências textuais sem alterar o conteúdo dos documentos."""
import re
from aplicacao.servicos.recuperacao.consulta_textual import cobertura

TITULO = re.compile(r'(?m)^\s*(?:[0-9]+\.)+[0-9]*\s+([^\n]{3,120})$')
PONTILHADO = re.compile(r'\.{5,}|…{3,}')


def chave_classificacao(trecho, palavras):
    """Prefira conteúdo com título pertinente a entradas de sumário.

    Args:
        trecho: Evidência com pontuação de cobertura já calculada.
        palavras (set[str]): Assuntos relevantes da pergunta.

    Returns:
        tuple: Cobertura, presença de conteúdo e afinidade do título; empates mantêm BM25.
    """
    corpo = not bool(PONTILHADO.search(trecho.texto))
    titulos = TITULO.findall(trecho.texto)
    afinidade = max((cobertura(palavras, titulo) for titulo in titulos), default=0.0)
    direta = afinidade_direta(trecho.texto, palavras)
    return trecho.similaridade, corpo, direta, afinidade


def afinidade_direta(texto, palavras):
    """Destaque campos que respondem ao assunto sem priorizar sumários.

    Args:
        texto (str): Evidência candidata da recuperação textual.
        palavras (set[str]): Assuntos presentes na pergunta.

    Returns:
        int: Peso adicional de campos explícitos do projeto pedagógico.
    """
    from aplicacao.servicos.recuperacao.filtros_acervo import normalizar
    texto = normalizar(texto)
    regras = {'duracao': r'prazo de integralizacao.*minimo de',
              'disciplina': r'tabela de componentes|matriz curricular|[1-4]o.*semestre',
              'carga': r'carga horaria total', 'modalidade': r'modalidade',
              'horario': r'vagas e turnos'}
    return sum(bool(re.search(padrao, texto, re.S)) for chave, padrao in regras.items() if chave in palavras)
