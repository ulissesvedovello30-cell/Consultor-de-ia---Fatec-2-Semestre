"""Adaptador vetorial opcional com PDF e respostas remotas controladas."""
import json
import httpx
import pytest
from pypdf import PdfReader, PdfWriter
from aplicacao.configuracao import parametros as config
from aplicacao.configuracao.caminhos import DOCUMENTOS
from aplicacao.inicializacao import montagem
from aplicacao.infra.gemini.gemini_http import ClienteGemini, ErroGemini
from aplicacao.servicos.acervo import documentos_reais
from aplicacao.servicos.gemini.gemini import EmbeddingsGemini, GeradorGemini


class TransporteGemini:
    def __init__(self):
        self.metodos, self.falha = [], None

    def __call__(self, req):
        metodo = req.url.path.split(':')[-1]
        self.metodos.append(metodo)
        if self.falha == metodo:
            return httpx.Response(429, json={'error': {'details': [{'violations': [{'quotaId': 'EmbedRequestsPerDay', 'quotaValue': '0'}]}]}})
        return self.resposta(metodo, json.loads(req.content))

    def resposta(self, metodo, dados):
        vetor = {'values': [1.0] + [0.0] * 767}
        if metodo == 'batchEmbedContents':
            return httpx.Response(200, json={'embeddings': [vetor for _ in dados['requests']]})
        if metodo == 'embedContent':
            return httpx.Response(200, json={'embedding': vetor})
        texto = json.dumps({'status': 'respondida', 'trechos': [1]})
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': texto}]}}]})


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    escritor = PdfWriter()
    escritor.add_page(PdfReader(next(DOCUMENTOS.rglob('Calendario*.pdf'))).pages[0])
    pasta = tmp_path / 'documentos'
    pasta.mkdir()
    escritor.write(pasta / 'calendario.pdf')
    monkeypatch.setattr(documentos_reais, 'DOCUMENTOS', pasta)
    monkeypatch.setattr(config, 'SQLITE_CAMINHO', str(tmp_path / 'acervo.db'))
    monkeypatch.setattr(config, 'BUSCA_ACERVO', 'gemini')
    monkeypatch.setattr(config, 'GEMINI_API_KEY', 'chave-de-teste')
    transporte = TransporteGemini()
    monkeypatch.setattr(montagem, 'ClienteGemini', lambda chave: ClienteGemini(chave, httpx.MockTransport(transporte)))
    return transporte


def test_vetores_e_gerador_gemini_sem_fallback_local(ambiente):
    with montagem.abrir_chatbot() as (bot, base):
        assert isinstance(base._embedder, EmbeddingsGemini)
        assert isinstance(bot._consultor._gerador, GeradorGemini)
        assert base.total_trechos > 0
    quantidade = ambiente.metodos.count('batchEmbedContents')
    assert quantidade > 0
    with montagem.abrir_chatbot() as (_, base):
        assert base.total_trechos > 0
    assert ambiente.metodos.count('batchEmbedContents') == quantidade


def test_falha_na_indexacao_nao_e_confirmada(ambiente):
    ambiente.falha = 'batchEmbedContents'
    with pytest.raises(ErroGemini):
        with montagem.abrir_chatbot():
            pass
    ambiente.falha = None
    with montagem.abrir_chatbot() as (_, base):
        assert base.total_trechos > 0


def test_falta_chave_impede_ativacao(ambiente, monkeypatch):
    monkeypatch.setattr(config, 'GEMINI_API_KEY', '')
    with pytest.raises(ValueError, match='exige Gemini'):
        with montagem.abrir_chatbot():
            pass
    assert ambiente.metodos == []
