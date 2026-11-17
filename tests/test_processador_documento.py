import pytest

from servicos.processador_documento import dividir_em_trechos


def test_junta_paragrafos_curtos_no_mesmo_trecho():
    assert dividir_em_trechos("aaa\n\nbbb", tamanho=100, sobreposicao=10) == ["aaa\n\nbbb"]


def test_abre_novo_trecho_quando_passa_do_limite():
    texto = f"{'a' * 60}\n\n{'b' * 60}"
    assert dividir_em_trechos(texto, tamanho=100, sobreposicao=10) == ["a" * 60, "b" * 60]


def test_fatia_paragrafo_gigante_com_sobreposicao():
    texto = "0123456789" * 25  # 250 caracteres
    trechos = dividir_em_trechos(texto, tamanho=100, sobreposicao=20)

    assert all(len(t) <= 100 for t in trechos)
    assert trechos[1].startswith(trechos[0][-20:])  # o fim de um trecho reaparece no começo do próximo
    assert trechos[-1] == texto[-10:]


def test_cada_item_de_lista_vira_um_trecho_mesmo_sem_linha_em_branco():
    # Como o pypdf entrega listas de PDF: itens colados, só com quebra de linha.
    texto = "Calendário\n- Prova A: dia 10, sala 1.\n- Prova B: dia 12, sala 2.\n- Prova C: dia 14, sala 3."

    trechos = dividir_em_trechos(texto, tamanho=300, sobreposicao=50)

    assert trechos == ["Calendário", "- Prova A: dia 10, sala 1.", "- Prova B: dia 12, sala 2.", "- Prova C: dia 14, sala 3."]


def test_hifen_no_meio_da_linha_nao_separa_nada():
    texto = "Aula de segunda-feira\ncom a professora Ana - sala 5."

    assert dividir_em_trechos(texto, tamanho=300, sobreposicao=50) == [texto]


def test_texto_vazio_nao_gera_trechos():
    assert dividir_em_trechos("  \n\n  ") == []


@pytest.mark.parametrize("tamanho, sobreposicao", [(100, 100), (100, 150), (0, 0), (100, -1)])
def test_rejeita_configuracao_que_travaria_o_fatiamento(tamanho, sobreposicao):
    with pytest.raises(ValueError):
        dividir_em_trechos("texto", tamanho=tamanho, sobreposicao=sobreposicao)


# --- formatos de arquivo ---------------------------------------------------------------

from dominio.erros import ErroIndexacao
from servicos.processador_documento import extrair_paginas


def test_txt_vem_sem_pagina_e_aceita_utf8_ou_cp1252(tmp_path):
    utf8 = tmp_path / "a.txt"
    utf8.write_bytes("Prova às 19h\r\nSala 5".encode("utf-8"))  # bytes: write_text trocaria o \n pelo do Windows
    antigo = tmp_path / "b.txt"
    antigo.write_bytes("Prova às 19h".encode("cp1252"))

    assert extrair_paginas(utf8) == [(None, "Prova às 19h\nSala 5")]
    assert extrair_paginas(antigo) == [(None, "Prova às 19h")]


def test_arquivo_vazio_e_formato_desconhecido_dao_erro_claro(tmp_path):
    vazio = tmp_path / "vazio.txt"
    vazio.write_text("   \n", encoding="utf-8")
    planilha = tmp_path / "notas.xlsx"
    planilha.write_bytes(b"x")

    with pytest.raises(ErroIndexacao, match="vazio"):
        extrair_paginas(vazio)
    with pytest.raises(ErroIndexacao, match="não suportado"):
        extrair_paginas(planilha)


def test_docx_junta_paragrafos_e_transforma_cada_linha_de_tabela_em_um_fato(tmp_path):
    docx = pytest.importorskip("docx")
    documento = docx.Document()
    documento.add_paragraph("Calendário de provas")
    tabela = documento.add_table(rows=2, cols=3)
    for linha, valores in zip(tabela.rows, [("Banco de Dados", "11/11", "Sala 5"), ("Inglês", "27/11", "Sala 3")]):
        for celula, valor in zip(linha.cells, valores):
            celula.text = valor
    caminho = tmp_path / "provas.docx"
    documento.save(str(caminho))

    (pagina, texto), = extrair_paginas(caminho)
    trechos = dividir_em_trechos(texto, tamanho=300, sobreposicao=50)

    assert pagina is None
    assert trechos == ["Calendário de provas", "- Banco de Dados | 11/11 | Sala 5", "- Inglês | 27/11 | Sala 3"]
