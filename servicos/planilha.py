"""Leia planilhas Excel (.xlsx) como fatos: horários de aula viram uma linha por dia e horário.

O formato esperado de horário é o usado pela Fatec: um bloco por semestre ('1° Semestre'),
dias da semana na linha seguinte, horários na primeira coluna e, em cada horário, a
disciplina numa linha e o professor na linha de baixo. Planilhas sem esse formato são lidas
linha a linha, usando a primeira linha como cabeçalho.
"""
import re
import unicodedata
from datetime import date, datetime

from dominio.erros import ErroIndexacao

LIMITE_LINHAS = 2000
LIMITE_COLUNAS = 64  # formatação esticada até a coluna XFB não pode virar milhares de células lidas
DIAS = ('segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo')
BLOCO = re.compile(r'^\s*(\d+)\s*[°ºo.]?\s*semestre\s*$', re.I)
HORARIO = re.compile(r'^\s*(\d{1,2}h(?:\d{2})?)\s*[-–]\s*(\d{1,2}h(?:\d{2})?)\s*$')
PREPOSICOES = {'de', 'da', 'do', 'das', 'dos', 'e'}


def extrair_xlsx(caminho):
    """Retorne o conteúdo visível da planilha como fatos; recuse planilha sem texto.

    Args:
        caminho: Arquivo .xlsx já inspecionado pela camada de segurança.

    Returns:
        Lista com um par (None, texto): planilhas não têm páginas.

    Raises:
        ErroIndexacao: Arquivo ilegível ou sem nenhum conteúdo de texto.
    """
    abas = [(aba.title, grade_da_aba(aba)) for aba in abrir_planilha(caminho).worksheets
            if aba.sheet_state == 'visible']
    horarios = [(grade, blocos_horario(grade)) for _, grade in abas]
    horarios = [(grade, blocos) for grade, blocos in horarios if blocos]
    fatos = fatos_de_horarios(caminho.stem, horarios) if horarios else fatos_de_tabelas(caminho.stem, abas)
    if not fatos:
        raise ErroIndexacao('A planilha não tem texto.')
    return [(None, '\n\n'.join(fatos))]


def abrir_planilha(caminho):
    """Abra o XLSX com valores calculados e sem vínculos externos; converta falhas em ErroIndexacao."""
    try:
        import openpyxl
        return openpyxl.load_workbook(caminho, data_only=True, keep_links=False)
    except Exception as erro:
        raise ErroIndexacao('Não foi possível ler o XLSX. Confira o arquivo e openpyxl.') from erro


def texto_da_celula(valor):
    """Converta o valor de uma célula em texto de uma linha, vazio quando não há conteúdo."""
    if valor is None:
        return ''
    if isinstance(valor, (datetime, date)):
        return valor.strftime('%d/%m/%Y')
    return ' '.join(str(valor).split())


class Grade(dict):
    """Células com texto, {(linha, coluna): texto}; `herdadas` marca as preenchidas por mesclagem."""

    def __init__(self):
        """Comece vazia, sem células herdadas."""
        super().__init__()
        self.herdadas = set()


def grade_da_aba(aba):
    """Leia as células com texto dentro dos limites e espalhe o valor de células mescladas."""
    linhas, colunas = min(aba.max_row or 0, LIMITE_LINHAS), min(aba.max_column or 0, LIMITE_COLUNAS)
    grade = Grade()
    for linha in aba.iter_rows(min_row=1, max_row=linhas, max_col=colunas):
        grade.update({(c.row, c.column): t for c in linha if (t := texto_da_celula(c.value))})
    for faixa in aba.merged_cells.ranges:
        espalhar(grade, faixa, linhas, colunas)
    return grade


def espalhar(grade, faixa, linhas, colunas):
    """Copie o valor do canto da faixa mesclada para as demais células dentro dos limites."""
    origem = grade.get((faixa.min_row, faixa.min_col))
    if not origem:
        return
    for linha in range(faixa.min_row, min(faixa.max_row, linhas) + 1):
        for coluna in range(faixa.min_col, min(faixa.max_col, colunas) + 1):
            if (linha, coluna) not in grade:
                grade[(linha, coluna)] = origem
                grade.herdadas.add((linha, coluna))


def sem_acento(texto):
    """Retorne o texto em minúsculas e sem acentos, para reconhecer os dias da semana."""
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if not unicodedata.combining(c))


def dias_abaixo(grade, linha, coluna):
    """Retorne {coluna: dia} para os dias da semana encontrados à direita do título do bloco."""
    achados = {c: grade[(linha, c)] for c in range(coluna + 1, coluna + 8)
               if (linha, c) in grade and sem_acento(grade[(linha, c)]).startswith(DIAS)}
    return achados if len(achados) >= 2 else {}


def blocos_horario(grade):
    """Ache títulos 'N° Semestre' com dias da semana logo abaixo; ignore os demais títulos."""
    blocos = []
    for (linha, coluna), valor in sorted(grade.items()):
        achado = BLOCO.match(valor)
        dias = dias_abaixo(grade, linha + 1, coluna) if achado else {}
        if dias:
            blocos.append({'semestre': int(achado.group(1)), 'linha': linha, 'coluna': coluna, 'dias': dias})
    return blocos


def fatos_de_horarios(prefixo, horarios):
    """Gere os fatos de todos os blocos de horário e as observações que ficaram fora deles."""
    fatos, areas = [], []
    for grade, blocos in horarios:
        for bloco in blocos:
            slots = linhas_de_horario(grade, bloco, blocos)
            areas.append((grade, bloco, max(slots, default=bloco['linha']) + 1))
            fatos += [f for linha in slots for f in aulas_do_horario(prefixo, grade, bloco, linha)]
    return fatos + observacoes(prefixo, areas, horarios)


def linhas_de_horario(grade, bloco, blocos):
    """Liste as linhas com horário ('7h40-9h20') abaixo do título, até o próximo bloco da coluna."""
    seguintes = [b['linha'] for b in blocos if b['coluna'] == bloco['coluna'] and b['linha'] > bloco['linha']]
    limite = min(seguintes, default=LIMITE_LINHAS + 1)
    return [r for r in range(bloco['linha'] + 2, limite) if HORARIO.match(grade.get((r, bloco['coluna']), ''))]


def aulas_do_horario(prefixo, grade, bloco, linha):
    """Gere um fato por dia para o horário da linha: disciplina e, na linha de baixo, o professor."""
    inicio, fim = HORARIO.match(grade[(linha, bloco['coluna'])]).groups()
    professor_embaixo = (linha + 1, bloco['coluna']) not in grade  # rótulo vazio = linha de professores
    fatos = []
    for coluna, dia in bloco['dias'].items():
        disciplina = grade.get((linha, coluna))
        professor = grade.get((linha + 1, coluna)) if professor_embaixo else None
        if disciplina:
            fatos.append(montar_fato(prefixo, bloco['semestre'], dia, (inicio, fim), disciplina, professor))
    return fatos


def montar_fato(prefixo, semestre, dia, horario, disciplina, professor):
    """Escreva a aula em uma frase completa, para o trecho fazer sentido sozinho."""
    fato = f'- {prefixo}: {semestre}º semestre, {dia.lower()}, das {horario[0]} às {horario[1]}: {disciplina}'
    if professor and professor != disciplina:
        fato += f'. Professor(a): {nome_proprio(professor)}'
    return fato + '.'


def nome_proprio(nome):
    """Troque NOMES EM MAIÚSCULAS por Nomes Próprios; nomes já escritos normalmente ficam como estão."""
    if nome != nome.upper():
        return nome
    palavras = nome.lower().split()
    return ' '.join(p if p in PREPOSICOES else p.capitalize() for p in palavras)


def observacoes(prefixo, areas, horarios):
    """Transforme textos fora das grades (rodapés) em fatos, sem repetir nem incluir títulos soltos."""
    vistas = {}
    for grade, _ in horarios:
        for celula, valor in sorted(grade.items()):
            if e_observacao(celula, valor, grade, areas):
                vistas[valor] = f'- {prefixo}, observação: {valor}'
    return list(vistas.values())


def e_observacao(celula, valor, grade, areas):
    """Diga se é texto solto: escrito à mão (não herdado de mesclagem), fora dos blocos e que não seja rótulo."""
    return celula not in grade.herdadas and not dentro_de_alguma_area(celula, grade, areas) and not ruido(valor)


def dentro_de_alguma_area(celula, grade, areas):
    """Diga se a célula pertence a um bloco de horário (título, dias, horários e aulas)."""
    linha, coluna = celula
    return any(g is grade and b['linha'] <= linha <= fim and b['coluna'] <= coluna <= b['coluna'] + 7
               for g, b, fim in areas)


def ruido(valor):
    """Reconheça rótulos que não são observações: títulos de semestre, horários, dias e 'Intervalo'."""
    return bool(BLOCO.match(valor) or HORARIO.match(valor) or sem_acento(valor).startswith(DIAS)
                or valor.lower() == 'intervalo')


def fatos_de_tabelas(prefixo, abas):
    """Leia planilhas comuns: a primeira linha de cada aba é o cabeçalho e cada linha vira um fato."""
    fatos = []
    for titulo, grade in abas:
        por_linha = {}
        for (linha, coluna), valor in sorted(grade.items()):
            por_linha.setdefault(linha, {})[coluna] = valor
        cabecalho, *dados = por_linha.values() or [{}]
        fatos += [linha_da_tabela(prefixo, titulo, cabecalho, celulas) for celulas in dados]
    return fatos


def linha_da_tabela(prefixo, aba, cabecalho, celulas):
    """Escreva uma linha como 'coluna: valor; coluna: valor'."""
    partes = [f'{cabecalho[c]}: {v}' if c in cabecalho else v for c, v in sorted(celulas.items())]
    return f'- {prefixo}, aba {aba}: ' + '; '.join(partes) + '.'
