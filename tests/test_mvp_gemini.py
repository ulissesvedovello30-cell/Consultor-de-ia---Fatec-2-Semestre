"""Fluxo real do MVP com transporte HTTP Gemini substituído apenas no teste."""
import asyncio
import json
import re
import sys
from contextlib import contextmanager
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient
import config
import montagem
from dominio.erros import ErroGeracaoResposta
from infra.banco_de_dados import criar_engine
from infra.gemini_http import ClienteGemini, ErroGemini
from infra.inicializacao import carga_concluida
from infra.repositorio_trechos import identidade
from servicos.gemini import EmbeddingsGemini, GeradorGemini
from servicos.inicializar_acervo import preparar_primeira_carga
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash
from seguranca.totp import codigo


class TransporteGemini:
    def __init__(self):
        self.metodos = []
        self.falha = None

    def __call__(self, request):
        metodo = request.url.path.split(':')[-1]
        self.metodos.append(metodo)
        if self.falha == metodo:
            return httpx.Response(503, json={'error': 'falha simulada'})
        dados = json.loads(request.content)
        vetor = {'values': [1.0] + [0.0] * 767}
        if metodo == 'batchEmbedContents':
            return httpx.Response(200, json={'embeddings': [vetor for _ in dados['requests']]})
        if metodo == 'embedContent':
            return httpx.Response(200, json={'embedding': vetor})
        assert metodo == 'generateContent'
        texto = dados['contents'][0]['parts'][0]['text']
        trecho = re.search(r'\[Trecho 1 \| Fonte: [^\n]+\]\n(.*?)(?:\n\n---\n\n|\n\nPERGUNTA:)', texto, re.S)[1]
        resposta = json.dumps({'status': 'respondida', 'afirmacoes': [{'texto': trecho, 'fontes': [1]}]})
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': resposta}]}}]})


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    import servicos.acervo_institucional as acervo
    fontes = acervo.validar_fontes()
    monkeypatch.setattr(acervo, 'validar_fontes', lambda: [f for f in fontes if f['arquivo'].endswith('.txt')])
    monkeypatch.setattr(config, 'PERFIL', 'mvp')
    monkeypatch.setattr(config, 'SQLITE_CAMINHO', str(tmp_path / 'acervo.sqlite3'))
    monkeypatch.setattr(config, 'GEMINI_API_KEY', 'chave-de-teste')
    monkeypatch.setattr(config, 'BUSCA_ACERVO', 'gemini')
    monkeypatch.setattr(config, 'MODELO_GERADOR', 'modelo-de-teste')
    monkeypatch.setattr(config, 'MODELO_EMBEDDING', 'gemini-embedding-001')
    transporte = TransporteGemini()
    monkeypatch.setattr(montagem, 'ClienteGemini', lambda chave: ClienteGemini(chave, httpx.MockTransport(transporte)))
    return transporte, tmp_path


def test_bootstrap_persistencia_e_gemini_obrigatorio(ambiente):
    transporte, _ = ambiente
    with montagem.abrir_chatbot() as (bot, base):
        assert isinstance(base._embedder, EmbeddingsGemini)
        assert isinstance(bot._consultor._gerador, GeradorGemini)
        assert base.total_trechos == 8
        resposta = asyncio.run(bot.processar_mensagem('publica', 'Qual a mensalidade?'))
        assert resposta.sucesso and 'gratuitos' in resposta.texto
        assert 'generateContent' in transporte.metodos
    contagem = transporte.metodos.count('batchEmbedContents')
    with montagem.abrir_chatbot() as (bot, base):
        assert base.total_trechos == 8
        assert transporte.metodos.count('batchEmbedContents') == contagem
        base.repositorio.excluir(identidade('FAQ_secretaria.txt'))
    with montagem.abrir_chatbot() as (_, base):
        assert base.total_trechos == 0
        assert transporte.metodos.count('batchEmbedContents') == contagem


def test_inicio_interrompido_retoma_sem_confirmar_carga(ambiente):
    transporte, _ = ambiente
    transporte.falha = 'batchEmbedContents'
    with pytest.raises(ErroGemini):
        with montagem.abrir_chatbot(): pass
    engine = criar_engine('mvp', config.SQLITE_CAMINHO)
    assert not carga_concluida(engine)
    engine.dispose()
    transporte.falha = None
    with montagem.abrir_chatbot() as (_, base): assert base.total_trechos == 8


def test_falta_chave_nao_ativa_gerador_local(ambiente, monkeypatch):
    transporte, pasta = ambiente
    monkeypatch.setattr(config, 'GEMINI_API_KEY', '')
    with pytest.raises(ValueError, match='exige Gemini'):
        with montagem.abrir_chatbot(): pass
    assert not (pasta / 'acervo.sqlite3').exists() and not transporte.metodos


def test_falha_geracao_nao_usa_resposta_offline(ambiente):
    transporte, _ = ambiente
    with montagem.abrir_chatbot() as (bot, _):
        transporte.falha = 'generateContent'
        resposta = asyncio.run(bot.processar_mensagem('p', 'Qual a mensalidade?'))
        assert not resposta.sucesso and resposta.estado == 'indisponivel'
        assert 'gratuitos' not in resposta.texto


def test_api_mvp_login_2fa_upload_exclusao_e_reinicio(ambiente):
    transporte, pasta = ambiente
    segredo = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
    cfg = ConfigWeb(origem='http://testserver', usuario='teste@gmail.com', senha_hash=gerar_hash('senha-teste-123456'),
                    totp_segredo=segredo, seguranca_db=str(pasta / 'login.db'))
    with TestClient(criar_app(configuracao=cfg)) as c:
        sessao = c.get('/api/sessao').json()
        assert sessao['exige_2fa']
        c.headers['X-CSRF-Token'] = sessao['csrf']
        assert c.get('/api/info').json()['modo'] == 'mvp'
        assert c.post('/api/chat', json={'texto': 'Qual a mensalidade?'}).json()['sucesso']
        credenciais = {'usuario': cfg.usuario, 'senha': 'senha-teste-123456'}
        assert c.post('/api/admin/login', json=credenciais).status_code == 401
        c.app.state.protecao_login.relogio = lambda: 1234567890
        credenciais['otp'] = codigo(segredo, 1234567890 // 30)
        login = c.post('/api/admin/login', json=credenciais)
        assert login.status_code == 200
        c.headers['X-CSRF-Token'] = login.json()['csrf']
        dados = {'nome': 'publicacao.txt', 'publico': 'true'}
        assert c.post('/api/admin/documentos', params=dados, content=b'Os cursos sao gratuitos.').status_code == 200
        transporte.falha = 'batchEmbedContents'
        assert c.post('/api/admin/documentos', params=dados, content=b'Houve uma atualizacao do curso.').status_code == 503
        transporte.falha = None
        publicados = c.get('/api/admin/documentos').json()
        doc = next(d for d in publicados if d['nome'] == 'publicacao.txt')
        assert 'gratuitos' in c.get(f"/api/fontes/{doc['documento_id']}/{doc['id_1']}").text
        assert c.delete(f"/api/admin/documentos/{doc['documento_id']}").status_code == 200
    with montagem.abrir_chatbot() as (_, base):
        assert [d['nome'] for d in base.repositorio.listar()] == ['FAQ_secretaria.txt']


def test_mvp_nao_libera_admin_sem_totp(ambiente):
    _, pasta = ambiente
    cfg = ConfigWeb(origem='http://testserver', senha_hash=gerar_hash('senha-teste-123456'), seguranca_db=str(pasta / 'login.db'))
    with TestClient(criar_app(configuracao=cfg)) as c:
        c.headers['X-CSRF-Token'] = c.get('/api/sessao').json()['csrf']
        assert c.post('/api/admin/login', json={'usuario': 'admin', 'senha': 'senha-teste-123456'}).status_code == 503
        assert c.get('/api/admin/documentos').status_code == 401


def test_argumento_demo_removido_e_postgres_ainda_indisponivel(monkeypatch):
    import servidor
    monkeypatch.setattr(sys, 'argv', ['servidor.py', '--demo'])
    with pytest.raises(SystemExit) as erro: servidor.argumentos()
    assert erro.value.code == 2
    with pytest.raises(NotImplementedError): servidor.validar_perfil('postgres')
