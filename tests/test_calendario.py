"""Calendário acadêmico em PDF: cada evento deve carregar mês e ano, mesmo fora do bloco do mês."""
import calendar

from servicos.calendario import normalizar_calendario

SEMANA = 'Dom Seg Ter Qua Qui Sex Sáb'


def mes(nome, numero, ano, eventos):
    """Monte o texto de um mês como o pypdf entrega: cabeçalho, dias da semana, grade e eventos."""
    grade = '\n'.join(' '.join(str(d) if d else ' ' for d in semana).rstrip()
                      for semana in calendar.Calendar(firstweekday=6).monthdayscalendar(ano, numero))
    return f'   {nome} {ano}  \n{SEMANA} \n{grade} \n \n' + '\n'.join(eventos) + '\n'


def fatos(paginas):
    return [bloco for _, texto in paginas for bloco in texto.split('\n\n')]


def converter(*textos):
    return normalizar_calendario(list(enumerate(textos, 1)))


def tres_meses(*eventos_fevereiro):
    return mes('fevereiro', 2, 2026, eventos_fevereiro) + mes('março', 3, 2026, ['05 Evento de março']) + \
        mes('abril', 4, 2026, ['06 Evento de abril'])


def test_evento_ganha_dia_mes_ano_e_dia_da_semana():
    resultado = fatos(converter(tres_meses('04 Início do 1º Semestre de 2026')))

    assert '- Dia 4 de fevereiro de 2026 (quarta-feira): Início do 1º Semestre de 2026' in resultado
    assert '- Dia 5 de março de 2026 (quinta-feira): Evento de março' in resultado
    assert '- Dia 6 de abril de 2026 (segunda-feira): Evento de abril' in resultado


def test_periodos_e_dias_avulsos():
    resultado = fatos(converter(tres_meses('04 a 07 Semana de Práticas', '12 e 13 Matrícula do itinerário')))

    assert '- De 4 a 7 de fevereiro de 2026: Semana de Práticas' in resultado
    assert '- Dias 12 e 13 de fevereiro de 2026: Matrícula do itinerário' in resultado


def test_grade_do_mes_nao_vira_evento_nem_fica_no_texto():
    resultado = fatos(converter(tres_meses('04 Início das aulas')))

    assert len(resultado) == 3 and all(f.startswith('- Dia') for f in resultado)
    assert not any('Dom Seg' in f or '1 2 3 4' in f for f in resultado)


def test_dia_sozinho_na_linha_junta_as_linhas_seguintes_do_evento():
    resultado = fatos(converter(tres_meses('19', 'SIGA envia e-mail aos alunos', 'cancelamento da sua matrícula (Art. 28)')))

    assert '- Dia 19 de fevereiro de 2026 (quinta-feira): SIGA envia e-mail aos alunos cancelamento da sua matrícula (Art. 28)' in resultado


def test_data_dividida_em_duas_linhas_e_data_a_definir():
    resultado = fatos(converter(tres_meses('24/03 a ', '06/04 ', 'Previsão do período de inscrições', 'A definir Divulgação do resultado')))

    assert '- De 24 de março a 6 de abril de 2026: Previsão do período de inscrições' in resultado
    assert '- Data a definir (fevereiro de 2026): Divulgação do resultado' in resultado


def test_periodo_que_vira_o_ano():
    texto = mes('outubro', 10, 2026, []) + mes('novembro', 11, 2026, []) + mes('dezembro', 12, 2026, ['20/12 a 10/01 Recesso de fim de ano'])

    assert '- De 20 de dezembro de 2026 a 10 de janeiro de 2027: Recesso de fim de ano' in fatos(converter(texto))


def test_excedente_no_topo_da_pagina_volta_ao_primeiro_mes_da_pagina_anterior():
    # Neste layout o PDF coloca janeiro depois de fevereiro; o resto de fevereiro vai para a página seguinte.
    pagina_1 = mes('fevereiro', 2, 2026, ['04 Início do semestre']) + mes('janeiro', 1, 2026, ['01 Confraternização'])
    pagina_2 = '27 Divulgação de resultados\n28 Prazo final de matrículas\n' + mes('março', 3, 2026, ['05 Evento de março'])

    resultado = fatos(converter(pagina_1, pagina_2))

    assert '- Dia 27 de fevereiro de 2026 (sexta-feira): Divulgação de resultados' in resultado
    assert '- Dia 28 de fevereiro de 2026 (sábado): Prazo final de matrículas' in resultado
    assert '- Dia 1 de janeiro de 2026 (quinta-feira): Confraternização' in resultado


def test_a_pagina_original_do_evento_e_preservada():
    paginas = converter(mes('fevereiro', 2, 2026, ['04 A']) + mes('março', 3, 2026, ['05 B']), mes('abril', 4, 2026, ['06 C']))

    assert [n for n, _ in paginas] == [1, 2]
    assert 'Evento' not in fatos(paginas)[0] and '4 de fevereiro' in paginas[0][1] and '6 de abril' in paginas[1][1]


def test_notas_antes_da_grade_e_legenda_final_ficam_como_texto_comum():
    nota = 'Proposto pela CGESG.\nRetificado pela CGESG em 04/03/2026.\n'
    pagina_1 = '   janeiro 2026\n' + nota + SEMANA + '\n1 2 3\n4 5 6 7 8 9 10\n11 12 13 14 15 16 17\n18 19 20 21 22 23 24\n25 26 27 28 29 30 31\n01 Feriado\n'
    ultima = 'Legenda\nDomingos, feriados e emendas\n13 reposições + 107 dias letivos = 120 dias letivos\n'

    resultado = fatos(converter(pagina_1 + mes('fevereiro', 2, 2026, []) + mes('março', 3, 2026, []), ultima))

    assert 'Proposto pela CGESG. Retificado pela CGESG em 04/03/2026.' in resultado
    assert not any(f.startswith('- Dia 13') for f in resultado)
    assert any(f.startswith('Legenda') and '13 reposições' in f for f in resultado)


def test_texto_que_nao_parece_calendario_volta_sem_alteracao():
    paginas = [(1, '04 Início das aulas\n05 Prova'), (2, mes('maio', 5, 2026, ['01 Feriado']))]

    assert normalizar_calendario(paginas) is paginas


def test_data_inexistente_nao_quebra_a_conversao():
    resultado = fatos(converter(tres_meses('30 Evento impossível')))

    assert '- Dia 30 de fevereiro de 2026: Evento impossível' in resultado
