from contextlib import contextmanager
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from core.chatbot import Chatbot
from infra.esquema import metadata
from infra.repositorio_trechos import RepositorioTrechos
from servicos.base_conhecimento import BaseConhecimento
from servicos.consultor_rag import ConsultorRAG
from servicos.demo_offline import EmbeddingsLexicais, GeradorExtrativo
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash

SENHA = 'somente-teste-12345'


@pytest.fixture
def cliente(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'teste.sqlite3'),
                           connect_args={'check_same_thread': False})
    metadata.create_all(engine)
    base = BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    @contextmanager
    def fabrica():
        yield Chatbot(ConsultorRAG(base, GeradorExtrativo(), limiar_similaridade=0.2)), base
    cfg = ConfigWeb(origem='http://testserver', senha_hash=gerar_hash(SENHA), seguranca_db=str(tmp_path / 'seguranca.db'))
    with TestClient(criar_app(fabrica, cfg, 'debug'), raise_server_exceptions=False) as cliente:
        cliente.headers['X-CSRF-Token'] = cliente.get('/api/sessao').json()['csrf']
        yield cliente
    engine.dispose()


def entrar(cliente):
    resultado = cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': SENHA})
    assert resultado.status_code == 200, resultado.text
    cliente.headers['X-CSRF-Token'] = resultado.json()['csrf']


def enviar(cliente, texto='Prova de Banco de Dados dia 20 na sala 5.', nome='calendario.txt', **meta):
    return cliente.post('/api/admin/documentos', params={'nome': nome, 'publico': 'true', **meta}, content=texto.encode())


def test_consulta_publica_sem_login_e_painel_protegido(cliente):
    resposta = cliente.post('/api/chat', json={'texto': 'Quando é a prova?'})
    assert resposta.status_code == 200 and resposta.json()['estado'] == 'sem_resposta'
    assert cliente.get('/api/admin/documentos').status_code == 401
    assert enviar(cliente).status_code == 401
    assert cliente.delete('/api/admin/documentos/qualquer').status_code == 401


def test_login_invalido_nao_concede_acesso(cliente):
    resposta = cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': 'incorreta'})
    assert resposta.status_code == 401
    assert cliente.get('/api/admin/documentos').status_code == 401


def test_login_roda_no_servidor_rotaciona_cookie_e_logout_revoga(cliente):
    anterior = cliente.cookies.get('consultor')
    entrar(cliente)
    assert cliente.cookies.get('consultor') != anterior
    cookie = cliente.cookies.get('consultor')
    assert cliente.get('/api/admin/documentos').status_code == 200
    assert cliente.post('/api/admin/logout').status_code == 200
    cliente.cookies.set('consultor', cookie)
    assert cliente.get('/api/admin/documentos').status_code == 401


def test_upload_consulta_atualizacao_exclusao_e_fonte_real(cliente):
    entrar(cliente)
    assert enviar(cliente).status_code == 200
    resposta = cliente.post('/api/chat', json={'texto': 'Quando é a prova de Banco de Dados?'}).json()
    assert resposta['sucesso'] and 'dia 20' in resposta['texto']
    assert 'dia 20' in cliente.get(resposta['fontes'][0]['url']).text
    assert enviar(cliente, 'Prova de Banco de Dados dia 25 na sala 8.').status_code == 200
    nova = cliente.post('/api/chat', json={'texto': 'Quando é a prova de Banco de Dados?'}).json()
    assert 'dia 25' in nova['texto'] and 'dia 20' not in nova['texto']
    doc = cliente.get('/api/admin/documentos').json()[0]
    assert cliente.delete('/api/admin/documentos/' + doc['id']).status_code == 200
    assert cliente.get(nova['fontes'][0]['url']).status_code == 404
    assert not cliente.post('/api/chat', json={'texto': 'Quando é a prova?'}).json()['sucesso']


@pytest.mark.parametrize('nome', ['../segredo.txt', 'pasta\\a.txt', 'notas.csv', 'programa.exe'])
def test_upload_rejeita_caminhos_e_formatos(cliente, nome):
    entrar(cliente)
    assert enviar(cliente, nome=nome).status_code in {415, 422}
    assert cliente.get('/api/admin/documentos').json() == []


def test_metadados_invalidos_nao_publicam(cliente):
    entrar(cliente)
    assert enviar(cliente, inicio='2026-12-01', fim='2026-01-01').status_code == 422
    assert enviar(cliente, url_oficial='javascript:alert(1)').status_code == 422
    assert enviar(cliente, ano='abc').status_code == 422


def test_pdf_falso_e_docx_invalido_nao_substituem_documento(cliente):
    entrar(cliente)
    assert enviar(cliente, nome='a.pdf').status_code == 422
    assert enviar(cliente, nome='a.docx').status_code == 422
    assert enviar(cliente, texto='').status_code == 422
    assert cliente.get('/api/admin/documentos').json() == []


def test_csrf_e_origem_sao_exigidos(cliente):
    entrar(cliente)
    assert enviar(cliente).status_code == 200
    doc = cliente.get('/api/admin/documentos').json()[0]
    url = '/api/admin/documentos/' + doc['id']
    assert cliente.delete(url, headers={'Origin': 'https://outro.site'}).status_code == 403
    assert cliente.delete(url, headers={'X-CSRF-Token': 'errado'}).status_code == 403
    assert len(cliente.get('/api/admin/documentos').json()) == 1


def test_cabecalhos_e_cookie(cliente):
    resposta = cliente.get('/')
    assert resposta.headers['X-Content-Type-Options'] == 'nosniff'
    assert resposta.headers['Cache-Control'] == 'no-store'
    with TestClient(cliente.app) as novo:
        cookie = novo.get('/api/sessao').headers['set-cookie']
        assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie


def test_validacao_nao_devolve_senha_nem_input(cliente):
    secreta = 'sigilo123' * 100
    resposta = cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': secreta})
    assert resposta.status_code == 422 and 'sigilo123' not in resposta.text


def test_host_invalido_e_corpo_grande(cliente):
    assert cliente.get('/', headers={'Host': 'evil.example'}).status_code == 400
    resposta = cliente.post('/api/chat', content=b'x' * 8193)
    assert resposta.status_code == 413


def test_documento_vencido_nao_responde(cliente):
    entrar(cliente)
    assert enviar(cliente, fim='2020-01-01').status_code == 200
    resposta = cliente.post('/api/chat', json={'texto': 'Quando é a prova?'})
    assert not resposta.json()['sucesso']


def test_limpar_apaga_contexto_do_backend(cliente):
    entrar(cliente)
    enviar(cliente)
    cliente.post('/api/chat', json={'texto': 'Quando é a prova?'})
    bot = cliente.app.state.chatbot
    assert bot._ultima_pergunta
    assert cliente.delete('/api/conversa').status_code == 200
    assert not bot._ultima_pergunta


def test_falha_banco_no_chat_e_health_e_controlada(cliente, monkeypatch):
    from dominio.erros import ErroBancoDeDados
    def falhar(*args):
        raise ErroBancoDeDados('senha=segredo')
    monkeypatch.setattr(cliente.app.state.base.repositorio, 'carregar', falhar)
    for resposta in [cliente.post('/api/chat', json={'texto': 'prova'}), cliente.get('/api/health')]:
        assert resposta.status_code == 503 and 'segredo' not in resposta.text


def test_limite_login_nao_depende_de_cookie(cliente):
    for _ in range(5):
        assert cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': 'x'}).status_code == 401
    cliente.cookies.clear()
    cliente.headers['X-CSRF-Token'] = cliente.get('/api/sessao').json()['csrf']
    assert cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': SENHA}).status_code == 429
