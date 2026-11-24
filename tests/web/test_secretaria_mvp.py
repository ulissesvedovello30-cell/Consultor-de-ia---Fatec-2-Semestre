"""Login configurado e publicação real de PDFs no RAG textual persistente."""
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import httpx
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from aplicacao.core.chatbot import Chatbot
from aplicacao.infra.gemini.gemini_http import ClienteGemini
from aplicacao.infra.persistencia.sqlite import abrir_sqlite
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_textual import BaseTextual
from aplicacao.servicos.gemini.gemini import GeradorGemini
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.web.aplicacao import criar_app
from aplicacao.web.configuracao import ConfigWeb
from aplicacao.web.administracao import uploads
from aplicacao.web.administracao.senhas import conferir
from tests.apoio.pdf_publico import criar_pdf

RAIZ = Path(__file__).resolve().parents[2]
PERGUNTA = 'Onde fica o Laboratorio de Cartografia da Fatec?'
TEXTO = 'O Laboratorio de Cartografia da Fatec fica na sala 42 do bloco norte.'
CREDENCIAIS = {'usuario': 'admin', 'senha': 'admin', 'otp': '123456'}


def config_demo(pasta, origem='http://testserver'):
    dados = dotenv_values(RAIZ / '.env')
    return ConfigWeb(origem=origem, usuario=dados['ADMIN_USUARIO'], senha_hash=dados['ADMIN_SENHA_HASH'],
        demonstracao=dados['ADMIN_DEMONSTRACAO'] == 'true', codigo_demonstracao=dados['ADMIN_CODIGO_DEMONSTRACAO'],
        seguranca_db=str(pasta / 'seguranca.sqlite3'))


@contextmanager
def abrir_cliente(pasta):
    @contextmanager
    def fabrica():
        engine = abrir_sqlite(str(pasta / 'acervo.sqlite3'))
        api = ClienteGemini('teste', httpx.MockTransport(resposta_gemini))
        base = BaseTextual(RepositorioTrechos(engine)); base.carregar()
        gerador = GeradorGemini(api, 'gemini-2.5-flash')
        try:
            yield Chatbot(ConsultorRAG(base, gerador, limiar_similaridade=0.6)), base
        finally:
            api.fechar(); engine.dispose()
    with TestClient(criar_app(fabrica, config_demo(pasta), 'mvp')) as cliente:
        cliente.headers['X-CSRF-Token'] = cliente.get('/api/sessao').json()['csrf']
        yield cliente


def resposta_gemini(requisicao):
    assert requisicao.url.path.endswith(':generateContent')
    texto = json.dumps({'status': 'respondida', 'trechos': [1]})
    return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP',
        'content': {'parts': [{'text': texto}]}}]})


def entrar(cliente, **campos):
    resposta = cliente.post('/api/admin/login', json={**CREDENCIAIS, **campos})
    if resposta.status_code == 200:
        cliente.headers['X-CSRF-Token'] = resposta.json()['csrf']
    return resposta


def enviar_pdf(cliente, texto=TEXTO, nome='laboratorio.pdf'):
    return cliente.post('/api/admin/documentos', params={'nome': nome, 'publico': True},
        headers={'Content-Type': 'application/pdf'}, content=criar_pdf(texto))


@pytest.mark.parametrize('arquivo', ['.env', '.env.example'])
def test_pacote_traz_acesso_pronto_sem_alterar_politica_de_senha(arquivo):
    dados = dotenv_values(RAIZ / arquivo)
    assert dados['ADMIN_USUARIO'] == 'admin'
    assert conferir('admin', dados['ADMIN_SENHA_HASH'])
    assert dados['ADMIN_DEMONSTRACAO'] == 'true' and dados['ADMIN_CODIGO_DEMONSTRACAO'] == '123456'
    assert not conferir('incorreta', dados['ADMIN_SENHA_HASH'])


@pytest.mark.parametrize('campos', [{'usuario': 'outro'}, {'senha': 'errada'}, {'otp': '000000'}, {'otp': ''}])
def test_demo_exige_os_tres_campos(tmp_path, campos):
    with abrir_cliente(tmp_path) as cliente:
        sessao = cliente.get('/api/sessao').json()
        assert sessao['exige_2fa'] and sessao['demonstracao'] and not sessao['admin']
        assert entrar(cliente, **campos).status_code == 401
        assert cliente.get('/api/admin/documentos').status_code == 401
        assert enviar_pdf(cliente).status_code == 401


def test_codigo_demo_pode_ser_reutilizado_apos_logout(tmp_path):
    with abrir_cliente(tmp_path) as cliente:
        for _ in range(2):
            anterior = cliente.cookies.get('consultor')
            assert entrar(cliente).status_code == 200
            assert cliente.cookies.get('consultor') != anterior
            assert cliente.get('/api/admin/documentos').status_code == 200
            assert cliente.post('/api/admin/logout').status_code == 200
            cliente.headers['X-CSRF-Token'] = cliente.get('/api/sessao').json()['csrf']
            assert cliente.get('/api/admin/documentos').status_code == 401


def test_pdf_recebido_e_consultavel_persiste_substitui_e_exclui(tmp_path):
    with abrir_cliente(tmp_path) as cliente:
        assert not cliente.post('/api/chat', json={'texto': PERGUNTA}).json()['sucesso']
        assert entrar(cliente).status_code == 200
        enviado = enviar_pdf(cliente)
        assert enviado.status_code == 200, enviado.text
        assert enviado.json()['estado'] == 'indexado' and enviado.json()['trechos'] > 0
        resposta = cliente.post('/api/chat', json={'texto': PERGUNTA}).json()
        assert resposta['sucesso'] and 'sala 42' in resposta['texto'] and not resposta['fontes']
    with abrir_cliente(tmp_path) as cliente:
        assert entrar(cliente).status_code == 200
        assert cliente.get('/api/admin/documentos').json()[0]['nome'] == 'laboratorio.pdf'
        resposta = cliente.post('/api/chat', json={'texto': PERGUNTA}).json()
        assert resposta['sucesso'] and 'sala 42' in resposta['texto']
        assert enviar_pdf(cliente, TEXTO.replace('42', '73')).status_code == 200
        resposta = cliente.post('/api/chat', json={'texto': PERGUNTA}).json()
        assert resposta['sucesso'] and 'sala 73' in resposta['texto'] and 'sala 42' not in resposta['texto']
        documento = cliente.get('/api/admin/documentos').json()[0]
        assert cliente.delete('/api/admin/documentos/' + documento['id']).status_code == 200
        assert not cliente.post('/api/chat', json={'texto': PERGUNTA}).json()['sucesso']


def test_pdf_invalido_nao_apaga_versao_ja_publicada(tmp_path):
    with abrir_cliente(tmp_path) as cliente:
        entrar(cliente); assert enviar_pdf(cliente).status_code == 200
        resposta = cliente.post('/api/admin/documentos', params={'nome': 'laboratorio.pdf', 'publico': True}, content=b'%PDF-falso')
        assert resposta.status_code == 422
        assert 'sala 42' in cliente.post('/api/chat', json={'texto': PERGUNTA}).json()['texto']
        assert cliente.app.state.upload_vaga.acquire(blocking=False)
        cliente.app.state.upload_vaga.release()


def test_erro_ao_criar_pasta_libera_proximo_upload(tmp_path, monkeypatch):
    with abrir_cliente(tmp_path) as cliente:
        entrar(cliente)
        with monkeypatch.context() as contexto:
            def falhar(**kwargs):
                raise OSError('caminho-sigiloso')
            contexto.setattr(uploads.tempfile, 'mkdtemp', falhar)
            resposta = enviar_pdf(cliente)
            assert resposta.status_code == 503 and 'caminho-sigiloso' not in resposta.text
        assert enviar_pdf(cliente).status_code == 200


def test_demo_nao_dispensa_csrf_nem_revisao_publica(tmp_path):
    with abrir_cliente(tmp_path) as cliente:
        entrar(cliente)
        params = {'nome': 'documento.pdf', 'publico': True}
        assert cliente.post('/api/admin/documentos', params=params, content=criar_pdf(TEXTO),
            headers={'X-CSRF-Token': 'errado'}).status_code == 403
        assert cliente.post('/api/admin/documentos', params={'nome': 'documento.pdf'}, content=criar_pdf(TEXTO)).status_code == 422
        assert cliente.get('/api/admin/documentos').json() == []


def test_codigo_fixo_nao_libera_acesso_normal_sem_totp(tmp_path):
    cfg = replace(config_demo(tmp_path), demonstracao=False)
    with abrir_cliente(tmp_path) as cliente:
        cliente.app.state.protecao_login.config = cfg
        assert entrar(cliente).status_code == 503
        assert cliente.get('/api/admin/documentos').status_code == 401


def test_demo_requer_origem_local_e_codigo_de_seis_digitos(tmp_path):
    cfg = config_demo(tmp_path)
    with pytest.raises(ValueError, match='origem local'):
        replace(cfg, origem='https://secretaria.example.com')
    with pytest.raises(ValueError, match='seis dígitos'):
        replace(cfg, codigo_demonstracao='abc')
