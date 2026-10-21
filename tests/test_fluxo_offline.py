"""Fluxo completo sem rede, banco ou modelos: documento -> índice -> Chatbot."""
import asyncio

import pytest

from core.chatbot import Chatbot
from infra.repositorio_em_memoria import RepositorioEmMemoria
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.demo_offline import EmbeddingsLexicais, GeradorExtrativo

FATOS = """- Prova de Banco de Dados da turma do 2º semestre: quarta-feira, 11 de novembro de 2026, às 19h00, na sala 5.
- Prova de Inglês da turma do 2º semestre: sexta-feira, 27 de novembro de 2026, às 19h00, na sala 3.
- Evento Feira de Projetos da Fatec: sábado, 5 de dezembro de 2026, das 9h00 às 13h00, no pátio principal.
"""


@pytest.fixture
def chatbot(tmp_path):
    arquivo = tmp_path / "turma.txt"
    arquivo.write_text(FATOS, encoding="utf-8")
    base = BaseConhecimento(RepositorioEmMemoria(), EmbeddingsLexicais())
    assert base.indexar_arquivo(arquivo, tamanho_trecho=300) == 3  # um trecho por fato
    return Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.2))


def _perguntar(chatbot, texto):
    return asyncio.run(chatbot.processar_mensagem("1", texto))


def test_acha_a_prova_certa_e_cita_o_arquivo(chatbot):
    resposta = _perguntar(chatbot, "Quando é a prova de Banco de Dados?")

    assert resposta.sucesso
    assert "11 de novembro de 2026" in resposta.texto and "sala 5" in resposta.texto
    assert "[turma.txt]" in resposta.texto
    assert "Inglês" not in resposta.texto


def test_acha_o_evento(chatbot):
    resposta = _perguntar(chatbot, "Onde será a Feira de Projetos?")

    assert "pátio principal" in resposta.texto


def test_pergunta_fora_do_assunto_nao_inventa_resposta(chatbot):
    resposta = _perguntar(chatbot, "Qual a cor das girafas azuis?")

    assert not resposta.sucesso and "Não encontrei" in resposta.texto


def test_indexar_o_mesmo_arquivo_duas_vezes_nao_duplica(tmp_path):
    arquivo = tmp_path / "turma.txt"
    arquivo.write_text(FATOS, encoding="utf-8")
    base = BaseConhecimento(RepositorioEmMemoria(), EmbeddingsLexicais())

    assert base.indexar_arquivo(arquivo, tamanho_trecho=300) == 3
    assert base.indexar_arquivo(arquivo, tamanho_trecho=300) == 0
    assert base.total_trechos == 3
