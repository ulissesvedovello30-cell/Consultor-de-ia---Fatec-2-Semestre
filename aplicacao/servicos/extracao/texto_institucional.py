"""Limpeza de repetição visual dos PPCs, sem acrescentar fatos aos PDFs."""
import re

CABECALHOS = re.compile(r'(?m)^Projeto Pedagógico do CST[^\n]*\n(?:Corporativa\s*\n)?|'
                       r'^Fatec Rio Claro\s*$|^Pág\.\s*\d+\s*$')
CAMPOS = re.compile(r'(?m)^(Modalidade|Referência|Eixo tecnológico|Carga horária total|'
                   r'Duração da hora/aula|Período letivo|Vagas e turnos|Prazo de|Formas de acesso)\b')


def preparar_ppc(paginas):
    """Retire cabeçalhos repetidos somente de projetos pedagógicos identificáveis.

    Args:
        paginas (list): Pares de número da página e texto extraído.

    Returns:
        list: Páginas com os campos dos dados gerais separados para recuperação.
    """
    reconhecidos = sum('Projeto Pedagógico do CST' in t for _, t in paginas)
    if reconhecidos < 3:
        return paginas
    return [(n, limpar_pagina(t)) for n, t in paginas]


def limpar_pagina(texto):
    """Separe campos e remova marcas de diagramação preservando o conteúdo.

    Args:
        texto (str): Página original extraída de um PPC.

    Returns:
        str: Texto limpo, com parágrafos independentes para os dados gerais.
    """
    texto = CABECALHOS.sub('', texto)
    texto = re.sub(r'[\ue000-\uf8ff]', '', texto)
    texto = re.sub(r'Prazo de\s*\n\s*integralização', 'Prazo de integralização', texto)
    return CAMPOS.sub(r'\n\n- \1', texto).strip()
