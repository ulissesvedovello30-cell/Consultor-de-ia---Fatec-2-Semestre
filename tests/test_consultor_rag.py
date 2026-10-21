import asyncio

import pytest

from dominio.erros import ErroGeracaoResposta
from dominio.trecho_documento import TrechoDocumento
from servicos.consultor_rag import ConsultorRAG, RespostaRAG


class BaseFalsa:
    def __init__(self, trechos):
        self._trechos = trechos
        self.chamadas = 0

    def buscar(self, pergunta, k):
        self.chamadas += 1
        return self._trechos


class GeradorFalso:
    def __init__(self, resposta="resposta do modelo", erro=None):
        self._resposta = resposta
        self._erro = erro
        self.mensagens = None

    def gerar(self, mensagens):
        self.mensagens = mensagens
        if self._erro:
            raise self._erro
        return self._resposta


def _responder(consultor, pergunta):
    return asyncio.run(consultor.responder(pergunta))


def test_trecho_abaixo_do_limiar_nao_chega_ao_modelo():
    gerador = GeradorFalso()
    consultor = ConsultorRAG(BaseFalsa([TrechoDocumento("a.pdf", 1, "irrelevante", 0.10)]), gerador, limiar_similaridade=0.25)

    resposta = _responder(consultor, "qual o horário da biblioteca?")

    assert gerador.mensagens is None  # nem chamou o modelo: sem contexto bom, não há o que responder
    assert resposta.fontes == ()
    assert "Não encontrei" in resposta.texto


def test_trechos_relevantes_vao_no_contexto_com_arquivo_e_pagina():
    trechos = [TrechoDocumento("regimento.pdf", 12, "A biblioteca abre às 8h.", 0.8), TrechoDocumento("x.pdf", 1, "ruído", 0.1)]
    gerador = GeradorFalso("Abre às 8h [regimento.pdf, p. 12].")
    consultor = ConsultorRAG(BaseFalsa(trechos), gerador)

    resposta = _responder(consultor, "quando a biblioteca abre?")

    sistema, usuario = gerador.mensagens
    assert sistema["role"] == "system" and usuario["role"] == "user"
    assert "A biblioteca abre às 8h." in usuario["content"]
    assert "Fonte: regimento.pdf, p. 12" in usuario["content"]
    assert "ruído" not in usuario["content"]
    assert resposta.texto == "Abre às 8h [regimento.pdf, p. 12]."
    assert [f.pagina for f in resposta.fontes] == [12]


def test_pergunta_vazia_nao_busca_nem_gera():
    base, gerador = BaseFalsa([]), GeradorFalso()

    resposta = _responder(ConsultorRAG(base, gerador), "   ")

    assert base.chamadas == 0 and gerador.mensagens is None
    assert "Não encontrei" in resposta.texto


def test_pergunta_enorme_e_cortada_antes_de_ir_ao_modelo():
    gerador = GeradorFalso()
    consultor = ConsultorRAG(BaseFalsa([TrechoDocumento("a.pdf", 1, "texto", 0.9)]), gerador)

    _responder(consultor, "a" * 5000)

    assert "a" * 1000 in gerador.mensagens[1]["content"]
    assert "a" * 1001 not in gerador.mensagens[1]["content"]


def test_falha_do_modelo_vira_erro_de_dominio_sem_vazar_detalhes():
    gerador = GeradorFalso(erro=RuntimeError("CUDA out of memory em /home/fulano"))
    consultor = ConsultorRAG(BaseFalsa([TrechoDocumento("a.pdf", 1, "texto", 0.9)]), gerador)

    with pytest.raises(ErroGeracaoResposta) as erro:
        _responder(consultor, "pergunta")

    assert "fulano" not in str(erro.value)


def test_fontes_aparecem_sem_repeticao_e_em_ordem():
    fontes = (TrechoDocumento("b.pdf", 3, "x"), TrechoDocumento("a.pdf", 9, "y"), TrechoDocumento("a.pdf", 9, "z"))

    texto = RespostaRAG("Resposta.", fontes).texto_com_fontes()

    assert texto == "Resposta.\n\nFontes:\n- a.pdf, p. 9\n- b.pdf, p. 3"
    assert RespostaRAG("Sem fontes.", ()).texto_com_fontes() == "Sem fontes."


# --- resposta estruturada (JSON com fontes numeradas) ----------------------------------

import json


def _consultor_com_resposta_bruta(bruto):
    trechos = [
        TrechoDocumento("provas.pdf", 2, "Prova de BD dia 11/11 na sala 5.", 0.9),
        TrechoDocumento("eventos.txt", None, "Feira de Projetos dia 5/12.", 0.8),
    ]
    return ConsultorRAG(BaseFalsa(trechos), GeradorFalso(bruto))


def test_json_valido_vira_frases_com_citacao_em_cada_uma():
    bruto = json.dumps({"status": "respondida", "afirmacoes": [
        {"texto": "A prova de BD é dia 11/11.", "fontes": [1]},
        {"texto": "A Feira de Projetos é dia 5/12.", "fontes": [2, 2]},
    ]})

    resposta = _responder(_consultor_com_resposta_bruta(bruto), "quando são?")

    assert resposta.texto == (
        "A prova de BD é dia 11/11. [provas.pdf, p. 2]\n\nA Feira de Projetos é dia 5/12. [eventos.txt]"
    )
    assert resposta.fontes_no_texto and resposta.encontrou
    assert resposta.texto_com_fontes() == resposta.texto  # não repete as fontes no fim


def test_json_com_fonte_inexistente_nao_e_aceito():
    bruto = json.dumps({"status": "respondida", "afirmacoes": [{"texto": "Algo.", "fontes": [7]}]})

    resposta = _responder(_consultor_com_resposta_bruta(bruto), "pergunta")

    assert not resposta.encontrou and "Não encontrei" in resposta.texto


@pytest.mark.parametrize("fontes", [[True], [0], [], "1", [1.0]])
def test_fontes_mal_formadas_sao_recusadas(fontes):
    bruto = json.dumps({"status": "respondida", "afirmacoes": [{"texto": "Algo.", "fontes": fontes}]})

    assert not _responder(_consultor_com_resposta_bruta(bruto), "pergunta").encontrou


def test_status_insuficiente_vira_sem_resposta():
    bruto = json.dumps({"status": "insuficiente", "afirmacoes": []})

    resposta = _responder(_consultor_com_resposta_bruta(bruto), "pergunta")

    assert not resposta.encontrou and resposta.fontes == ()


def test_json_dentro_de_bloco_markdown_tambem_funciona():
    bruto = "```json\n" + json.dumps({"status": "respondida", "afirmacoes": [{"texto": "Dia 11/11.", "fontes": [1]}]}) + "\n```"

    assert _responder(_consultor_com_resposta_bruta(bruto), "pergunta").texto == "Dia 11/11. [provas.pdf, p. 2]"


def test_texto_livre_e_aproveitado_com_todas_as_fontes_no_fim():
    resposta = _responder(_consultor_com_resposta_bruta("A prova é dia 11/11."), "pergunta")

    assert resposta.encontrou and not resposta.fontes_no_texto
    assert resposta.texto_com_fontes() == "A prova é dia 11/11.\n\nFontes:\n- eventos.txt\n- provas.pdf, p. 2"
