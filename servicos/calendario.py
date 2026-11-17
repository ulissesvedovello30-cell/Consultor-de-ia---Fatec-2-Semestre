"""Converta calendários acadêmicos mensais em fatos datados, um por linha.

No PDF, o mês aparece só no cabeçalho do bloco e os eventos vêm como '04 Início das aulas'.
Ao fatiar o texto, o trecho '04 Início das aulas' perderia o mês. Aqui cada evento é
reescrito com dia, mês, ano e dia da semana, para que qualquer trecho seja entendido sozinho.
"""
import calendar
import re
from datetime import date

MESES = ('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
         'setembro', 'outubro', 'novembro', 'dezembro')
SEMANA = ('segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo')
CABECALHO = re.compile(r'^\s*(' + '|'.join(MESES) + r')\s+(\d{4})\s*$', re.I)
CABECALHO_SEMANA = re.compile(r'^\s*Dom\s+Seg\b')
GRADE = re.compile(r'^[\d\s]+$')
DIA = r'\d{1,2}(?:/\d{1,2})?'
EVENTO = re.compile(rf'^\s*(?P<datas>{DIA}(?:\s+[ae]\s+{DIA})?|a\s+definir)\b\s*(?P<resto>.*)$', re.I)
JUNCAO = re.compile(r'(\d{1,2}/\d{1,2})\s+a\s*\n\s*(\d{1,2}/\d{1,2})')
MINIMO_DE_MESES = 3


def normalizar_calendario(paginas):
    """Reescreva um calendário mensal como fatos datados; devolva a lista original se não for um.

    Args:
        paginas: Pares (número da página, texto) extraídos do PDF.

    Returns:
        Pares (número da página, texto) com um fato '- Dia 4 de fevereiro de 2026 (quarta-feira): ...'
        por evento. Páginas sem conteúdo são omitidas.
    """
    cabecalhos = sum(bool(CABECALHO.match(linha)) for _, texto in paginas for linha in texto.splitlines())
    if cabecalhos < MINIMO_DE_MESES:
        return paginas
    conversor = Conversor()
    convertidas = [(numero, conversor.pagina(texto)) for numero, texto in paginas]
    return [(numero, texto) for numero, texto in convertidas if texto]


class Conversor:
    """Percorra as páginas lembrando mês, grade do calendário e evento em andamento."""

    def __init__(self):
        """Comece sem mês definido: texto anterior ao primeiro cabeçalho segue como veio."""
        self.mes = self.ano = self.evento = None
        self.faltam = 0
        self.primeiro_anterior = self.primeiro_da_pagina = None
        self.blocos, self.livre = [], []

    def pagina(self, texto):
        """Converta uma página e retorne seus blocos separados por linha em branco."""
        self.blocos, self.primeiro_da_pagina = [], None
        self.retomar_mes_do_inicio()
        for linha in JUNCAO.sub(r'\1 a \2', texto).splitlines():
            self.linha(linha)
        self.fechar_evento()
        self.fechar_livre()
        self.primeiro_anterior = self.primeiro_da_pagina or self.primeiro_anterior
        return '\n\n'.join(self.blocos)

    def retomar_mes_do_inicio(self):
        """Atribua eventos soltos no topo da página ao 1º mês da página anterior.

        Neste layout o excedente de um mês continua na página seguinte, mas o PDF pode
        listar outro bloco (ex.: janeiro) entre os dois. Vale só para o formato observado.
        """
        if self.mes is not None and self.primeiro_anterior:
            self.mes, self.ano = self.primeiro_anterior
            self.faltam = 0

    def linha(self, linha):
        """Direcione uma linha: cabeçalho de mês, grade do mês, evento ou texto livre."""
        achado = CABECALHO.match(linha)
        if achado:
            return self.novo_mes(achado)
        if not linha.strip() or CABECALHO_SEMANA.match(linha):
            return None
        if linha.strip().lower().startswith('legenda'):
            return self.encerrar_calendario()
        if self.mes is not None and self.faltam and GRADE.match(linha):
            self.faltam = max(0, self.faltam - len(linha.split()))
            return None
        return self.texto(linha)

    def novo_mes(self, achado):
        """Registre o mês do cabeçalho e conte os dias da grade que precisam ser ignorados."""
        self.fechar_evento()
        self.fechar_livre()
        self.mes, self.ano = MESES.index(achado.group(1).lower()) + 1, int(achado.group(2))
        self.faltam = calendar.monthrange(self.ano, self.mes)[1]
        self.primeiro_da_pagina = self.primeiro_da_pagina or (self.mes, self.ano)

    def encerrar_calendario(self):
        """Pare de interpretar números como dias: o que vem depois da legenda é texto comum."""
        self.fechar_evento()
        self.fechar_livre()
        self.mes = None
        self.livre.append('Legenda')

    def texto(self, linha):
        """Abra evento, continue o evento aberto ou guarde como texto livre."""
        achado = EVENTO.match(linha) if self.mes is not None else None
        if achado and (not self.faltam or achado.group('resto').strip()):
            self.abrir_evento(achado)
        elif self.evento is not None:
            self.evento[2].append(linha.strip())
        else:
            self.livre.append(linha.strip())

    def abrir_evento(self, achado):
        """Inicie um evento datado; a grade não vale mais, pois já chegamos aos eventos."""
        self.fechar_evento()
        self.fechar_livre()
        self.faltam = 0
        self.evento = [achado.group('datas'), (self.mes, self.ano), [achado.group('resto')]]

    def fechar_evento(self):
        """Publique o evento aberto como um fato; descarte eventos sem descrição."""
        if self.evento is None:
            return
        datas, (mes, ano), partes = self.evento
        descricao = ' '.join(' '.join(partes).split())
        if descricao:
            self.blocos.append(f'- {descrever(datas, mes, ano)}: {descricao}')
        self.evento = None

    def fechar_livre(self):
        """Publique o texto acumulado fora de eventos (títulos, notas) como um parágrafo."""
        if self.livre:
            self.blocos.append(' '.join(self.livre))
            self.livre = []


def descrever(datas, mes, ano):
    """Escreva as datas por extenso, ex.: '04 a 07' em fevereiro de 2026."""
    if ' '.join(datas.lower().split()) == 'a definir':
        return f'Data a definir ({MESES[mes - 1]} de {ano})'
    if '/' in datas:
        return com_meses_explicitos(datas, ano)
    numeros = [int(n) for n in re.findall(r'\d+', datas)]
    sufixo = f' de {MESES[mes - 1]} de {ano}'
    if len(numeros) == 1:
        return f'Dia {numeros[0]}{sufixo}{dia_da_semana(numeros[0], mes, ano)}'
    return f'{ligar(datas, numeros)}{sufixo}'


def ligar(datas, numeros):
    """Escolha 'De X a Y' (período) ou 'Dias X e Y' (dias avulsos) conforme o texto original."""
    if re.search(r'\sa\s', datas, re.I):
        return f'De {numeros[0]} a {numeros[1]}'
    return f'Dias {numeros[0]} e {numeros[1]}'


def com_meses_explicitos(datas, ano):
    """Escreva datas no formato dd/mm; se algo for inválido, mantenha o texto original."""
    pares = [(int(d), int(m)) for d, m in re.findall(r'(\d{1,2})/(\d{1,2})', datas)]
    if not pares or not all(1 <= m <= 12 for _, m in pares):
        return datas
    if len(pares) == 1:
        dia, mes = pares[0]
        return f'Dia {dia} de {MESES[mes - 1]} de {ano}{dia_da_semana(dia, mes, ano)}'
    (d1, m1), (d2, m2) = pares[:2]
    ano_fim = ano + 1 if (m2, d2) < (m1, d1) else ano
    inicio = f'{d1} de {MESES[m1 - 1]}' + (f' de {ano}' if ano_fim != ano else '')
    return f'De {inicio} a {d2} de {MESES[m2 - 1]} de {ano_fim}'


def dia_da_semana(dia, mes, ano):
    """Retorne ' (quarta-feira)' ou vazio quando a data não existe no calendário."""
    try:
        return f' ({SEMANA[date(ano, mes, dia).weekday()]})'
    except ValueError:
        return ''
