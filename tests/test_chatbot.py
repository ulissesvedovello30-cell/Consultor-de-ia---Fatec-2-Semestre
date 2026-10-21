import asyncio

import pytest

from core.chatbot import Chatbot
from core.limitador import LimitadorTaxa
from dominio.erros import ErroGeracaoResposta
from dominio.trecho_documento import TrechoDocumento
from servicos.consultor_rag import RespostaRAG


class ConsultorFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta or RespostaRAG("Prova dia 10.", (TrechoDocumento("a.pdf", 1, "x"),), melhor_similaridade=0.8)
        self.erro = erro
        self.perguntas = []

    async def responder(self, pergunta):
        self.perguntas.append(pergunta)
        if self.erro:
            raise self.erro
        return self.resposta


class Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora


def _enviar(chatbot, texto, chat="1"):
    return asyncio.run(chatbot.processar_mensagem(chat, texto))


@pytest.mark.parametrize("texto", ["/start", "/ajuda", "/ajuda@MeuBot", "oi", "Olá!", "bom dia", "Boa noite."])
def test_comandos_e_saudacoes_mostram_a_ajuda_sem_chamar_o_modelo(texto):
    consultor = ConsultorFalso()

    resposta = _enviar(Chatbot(consultor), texto)

    assert resposta.texto == Chatbot.AJUDA and resposta.sucesso
    assert consultor.perguntas == []


def test_saudacao_com_pergunta_junto_vai_para_o_consultor():
    consultor = ConsultorFalso()

    _enviar(Chatbot(consultor), "oi, quando é a prova?")

    assert consultor.perguntas == ["oi, quando é a prova?"]


def test_comando_desconhecido():
    resposta = _enviar(Chatbot(ConsultorFalso()), "/entrar")

    assert "Comando desconhecido" in resposta.texto and not resposta.sucesso


@pytest.mark.parametrize("texto", ["", "   ", "a" * 1501])
def test_rejeita_mensagem_vazia_ou_enorme(texto):
    consultor = ConsultorFalso()

    resposta = _enviar(Chatbot(consultor), texto)

    assert not resposta.sucesso and consultor.perguntas == []


def test_resposta_traz_as_fontes_e_a_similaridade_como_nota():
    resposta = _enviar(Chatbot(ConsultorFalso()), "quando é a prova?")

    assert resposta.texto == "Prova dia 10.\n\nFontes:\n- a.pdf, p. 1"
    assert resposta.sucesso and resposta.score_qualidade == pytest.approx(0.8)


def test_limite_de_perguntas_por_conversa():
    chatbot = Chatbot(ConsultorFalso(), LimitadorTaxa(limite=1, janela=60))

    assert _enviar(chatbot, "primeira pergunta").sucesso
    bloqueada = _enviar(chatbot, "segunda pergunta")
    assert not bloqueada.sucesso and "Limite" in bloqueada.texto
    assert _enviar(chatbot, "outra conversa", chat="2").sucesso


def test_falha_do_modelo_vira_aviso_amigavel():
    resposta = _enviar(Chatbot(ConsultorFalso(erro=ErroGeracaoResposta("falhou"))), "quando é a prova?")

    assert not resposta.sucesso and "Tente novamente" in resposta.texto


def test_pergunta_com_referencia_leva_a_pergunta_anterior():
    consultor = ConsultorFalso()
    chatbot = Chatbot(consultor, LimitadorTaxa(limite=10, janela=60))

    _enviar(chatbot, "quando é a prova de Banco de Dados?")
    _enviar(chatbot, "e onde é isso?")

    assert consultor.perguntas[0] == "quando é a prova de Banco de Dados?"
    assert "quando é a prova de Banco de Dados?" in consultor.perguntas[1]
    assert "e onde é isso?" in consultor.perguntas[1]


def test_contexto_nao_vaza_entre_conversas_nem_depois_de_expirar():
    relogio = Relogio()
    consultor = ConsultorFalso()
    chatbot = Chatbot(consultor, LimitadorTaxa(limite=10, janela=60, relogio=relogio), relogio=relogio)

    _enviar(chatbot, "quando é a prova de Banco de Dados?", chat="1")
    _enviar(chatbot, "e onde é isso?", chat="2")
    assert consultor.perguntas[-1] == "e onde é isso?"  # outra conversa: sem contexto

    relogio.agora += Chatbot.SEGUNDOS_DE_CONTEXTO + 1
    _enviar(chatbot, "e onde é isso?", chat="1")
    assert consultor.perguntas[-1] == "e onde é isso?"  # contexto expirou


def test_pergunta_sem_resposta_nao_vira_contexto():
    consultor = ConsultorFalso(RespostaRAG("Não encontrei.", (), encontrou=False))
    chatbot = Chatbot(consultor, LimitadorTaxa(limite=10, janela=60))

    _enviar(chatbot, "qual a cor das girafas azuis?")
    _enviar(chatbot, "e isso?")

    assert consultor.perguntas[1] == "e isso?"


# --- teto de atendimentos simultâneos --------------------------------------------------

class ConsultorLento(ConsultorFalso):
    """Só responde quando o teste liberar, para manter atendimentos abertos ao mesmo tempo."""

    def __init__(self, liberar):
        super().__init__()
        self.liberar = liberar

    async def responder(self, pergunta):
        await self.liberar.wait()
        return await super().responder(pergunta)


def test_acima_do_teto_avisa_que_esta_ocupado_sem_gastar_o_limite_de_perguntas():
    async def cenario():
        liberar = asyncio.Event()
        chatbot = Chatbot(ConsultorLento(liberar), LimitadorTaxa(limite=1, janela=60), max_simultaneos=1)

        primeira = asyncio.create_task(chatbot.processar_mensagem("1", "pergunta um"))
        await asyncio.sleep(0)  # a primeira entra em atendimento
        ocupado = await chatbot.processar_mensagem("2", "pergunta dois")
        assert not ocupado.sucesso and "ocupado" in ocupado.texto

        liberar.set()
        assert (await primeira).sucesso
        # A conversa 2 não perdeu a cota por ter batido no teto:
        assert (await chatbot.processar_mensagem("2", "pergunta dois")).sucesso

    asyncio.run(cenario())


def test_erro_do_modelo_devolve_a_vaga_do_atendimento():
    consultor = ConsultorFalso(erro=ErroGeracaoResposta("falhou"))
    chatbot = Chatbot(consultor, LimitadorTaxa(limite=10, janela=60), max_simultaneos=1)

    assert "Tente novamente" in _enviar(chatbot, "primeira").texto
    assert "Tente novamente" in _enviar(chatbot, "segunda").texto  # se a vaga vazasse, viria "ocupado"
