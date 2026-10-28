"""Planilhas Excel: horário vira uma frase por dia/horário e o lixo de formatação é ignorado."""
from datetime import datetime

import pytest
from openpyxl import Workbook

from dominio.erros import ErroIndexacao
from seguranca.extracao import extrair_protegido
from servicos.processador_documento import extrair_paginas


def criar_horario(caminho):
    """Horário no formato da Fatec, com célula mesclada, rodapé e 'lixo' esticado para a direita."""
    pasta = Workbook()
    aba = pasta.active
    aba.title = 'Horario'
    aba['A1'] = '1° Semestre'
    aba.merge_cells('A1:F1')
    for coluna, dia in enumerate(['Segunda-feira', 'Terça-feira', 'Quarta-feira'], start=2):
        aba.cell(2, coluna, dia)
    aba['A3'], aba['B3'] = '7h40-9h20', 'Disciplinas Assíncronas\n(Moodle)'
    aba.merge_cells('B3:B8')
    aba['C3'], aba['C4'] = 'Projeto I ', 'CLEBERSON EUGÊNIO FORTE'
    aba['D3'], aba['D4'] = 'Estatística', 'FARID SALLUM NETO'
    aba['A5'] = 'Intervalo'
    aba['A6'], aba['C6'], aba['C7'] = '9h30-11h10', 'Projeto I', 'CLEBERSON EUGÊNIO FORTE'
    aba['A12'] = '2° Semestre'
    aba['B13'], aba['C13'] = 'Segunda-feira', 'Terça-feira'
    aba['A14'], aba['C14'], aba['C15'] = '7h40-9h20', 'Redes Neurais', 'Davi Duarte de Paula'
    aba['A20'] = 'Nos horários assíncronos os estudantes não precisam vir ao Campus'
    for coluna in range(70, 3000, 8):  # modelo esticado: milhares de títulos repetidos sem dias da semana
        aba.cell(1, coluna, '1° Semestre')
    pasta.create_sheet('Calculos')['A1'] = datetime(2005, 8, 1)
    pasta.save(caminho)
    return caminho


@pytest.fixture
def horario(tmp_path):
    return criar_horario(tmp_path / 'Horario Curso Teste.xlsx')


def fatos(caminho):
    (pagina, texto), = extrair_paginas(caminho)
    assert pagina is None
    return texto.split('\n\n')


def test_uma_frase_por_dia_e_horario_com_professor_em_nome_proprio(horario):
    resultado = fatos(horario)

    assert ('- Horario Curso Teste: 1º semestre, terça-feira, das 7h40 às 9h20: Projeto I. '
            'Professor(a): Cleberson Eugênio Forte.') in resultado
    assert '- Horario Curso Teste: 1º semestre, quarta-feira, das 7h40 às 9h20: Estatística. Professor(a): Farid Sallum Neto.' in resultado
    assert '- Horario Curso Teste: 2º semestre, terça-feira, das 7h40 às 9h20: Redes Neurais. Professor(a): Davi Duarte de Paula.' in resultado


def test_celula_mesclada_vale_para_todos_os_horarios_e_nao_vira_professor(horario):
    resultado = fatos(horario)

    assistida = [f for f in resultado if 'segunda-feira' in f and '1º semestre' in f]
    assert len(assistida) == 2 and all(f.endswith('Disciplinas Assíncronas (Moodle).') for f in assistida)


def test_ignora_titulos_repetidos_sem_dias_abas_de_calculo_e_rotulos(horario):
    resultado = fatos(horario)

    assert sum('1° Semestre' in f for f in resultado) == 0
    assert not any('2005' in f or 'Intervalo' in f or 'Calculos' in f for f in resultado)


def test_rodape_vira_observacao_uma_unica_vez(horario):
    resultado = fatos(horario)

    assert resultado.count('- Horario Curso Teste, observação: Nos horários assíncronos os estudantes não precisam vir ao Campus') == 1
    assert len(resultado) == 7  # 1º semestre: 3 + 2 aulas; 2º semestre: 1 aula; mais a observação


def test_planilha_comum_vira_fatos_com_o_cabecalho_como_rotulo(tmp_path):
    pasta = Workbook()
    aba = pasta.active
    aba.title = 'Eventos'
    aba.append(['Evento', 'Data', 'Local'])
    aba.append(['Feira de Projetos', datetime(2026, 12, 5), 'Pátio'])
    aba.append(['Palestra', datetime(2026, 11, 21), None])
    caminho = tmp_path / 'eventos.xlsx'
    pasta.save(caminho)

    assert fatos(caminho) == ['- eventos, aba Eventos: Evento: Feira de Projetos; Data: 05/12/2026; Local: Pátio.',
                              '- eventos, aba Eventos: Evento: Palestra; Data: 21/11/2026.']


def test_aba_oculta_nao_e_lida(tmp_path):
    pasta = Workbook()
    pasta.active.append(['Pública'])
    pasta.active.append(['dado visível'])
    oculta = pasta.create_sheet('Rascunho')
    oculta.append(['Interno'])
    oculta.append(['não publicar'])
    oculta.sheet_state = 'hidden'
    caminho = tmp_path / 'abas.xlsx'
    pasta.save(caminho)

    assert fatos(caminho) == ['- abas, aba Sheet: Pública: dado visível.']


def test_planilha_vazia_e_arquivo_corrompido_dao_erro_claro(tmp_path):
    vazia = tmp_path / 'vazia.xlsx'
    Workbook().save(vazia)
    corrompida = tmp_path / 'corrompida.xlsx'
    corrompida.write_bytes(b'isto nao e um zip')

    with pytest.raises(ErroIndexacao, match='não tem texto'):
        extrair_paginas(vazia)
    with pytest.raises(ErroIndexacao, match='XLSX'):
        extrair_paginas(corrompida)


def test_extracao_em_subprocesso_protegido_devolve_o_mesmo_resultado(horario):
    assert extrair_protegido(horario) == extrair_paginas(horario)
