"""A recusa do provedor não deve parecer ausência de informação no acervo."""
import asyncio
from contextlib import contextmanager
import httpx
from fastapi.testclient import TestClient
from aplicacao.core.chatbot import Chatbot
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.infra.gemini.gemini_http import ClienteGemini
from aplicacao.servicos.gemini.gemini import GeradorGemini
from aplicacao.web.aplicacao import criar_app
from aplicacao.web.configuracao import ConfigWeb


def test_cota_diaria_e_informada_como_limite_e_nao_como_busca_vazia(base_pdf, tmp_path):
    falha = {'error': {'details': [{'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaValue': '20'}]}]}}
    api = ClienteGemini('chave-nao-real', httpx.MockTransport(lambda r: httpx.Response(429, json=falha)))
    @contextmanager
    def fabrica():
        yield Chatbot(ConsultorRAG(base_pdf, GeradorGemini(api, 'gemini-3.5-flash'), limiar_similaridade=0.6)), base_pdf
    cfg = ConfigWeb(origem='http://testserver', seguranca_db=str(tmp_path / 'login.db'))
    try:
        with TestClient(criar_app(fabrica, cfg, 'teste')) as c:
            c.headers['X-CSRF-Token'] = c.get('/api/sessao').json()['csrf']
            r = c.post('/api/chat', json={'texto': 'Quanto dura os cursos?'})
            assert r.status_code == 429 and r.json()['estado'] == 'cota'
            assert 'limite de uso' in r.json()['texto'] and 'Não encontrei' not in r.json()['texto']
    finally:
        api.fechar()
