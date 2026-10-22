"""Testes de entradas hostis nas fronteiras HTTP/JSON e de capacidade finita."""
import asyncio
import inspect
import pytest
import uvicorn
from starlette.exceptions import HTTPException
from seguranca.entrada import cabecalhos, preparar
from seguranca.corpo import LeitorLimitado, ler_json
from seguranca.trafego import ControleTrafego
from seguranca.servidor import proxies_confiaveis, opcoes_uvicorn
from tests.test_web import cliente, entrar


@pytest.mark.parametrize('bruto', [b'{', b'[]', b'null', b'{"texto":"a","texto":"b"}',
    b'{"texto":NaN}', b'{"texto":Infinity}', b'{"texto":"\xff"}',
    b'{"texto":[[[[["a"]]]]]}', b'{"texto":"a","x":{"a":1,"a":2}}'])
def test_json_ambiguo_recusado(cliente, bruto):
    resposta = cliente.post('/api/chat', content=bruto, headers={'Content-Type':'application/json'})
    assert resposta.status_code == 400
    assert resposta.headers['X-Content-Type-Options'] == 'nosniff'


@pytest.mark.parametrize('dados', [{'texto':'prova', 'admin':True}, {'texto':123}, {'texto':True},
    {'texto':None}, {'texto':['prova']}, {'texto':'prova\x00'}, {'texto':'\ud800'}])
def test_schema_estrito_recusa_privilegios_tipos_e_unicode(cliente, dados):
    import json
    resposta = cliente.post('/api/chat', content=json.dumps(dados), headers={'Content-Type':'application/json'})
    assert resposta.status_code == 422
    assert cliente.get('/api/admin/documentos').status_code == 401


def test_login_nao_aceita_admin_injetado(cliente):
    resposta = cliente.post('/api/admin/login', json={'usuario':'admin','senha':'errada','admin':True})
    assert resposta.status_code == 422
    assert cliente.get('/api/admin/documentos').status_code == 401


@pytest.mark.parametrize('tipo', ['text/plain', 'application/x-www-form-urlencoded','application/json;charset=iso-8859-1'])
def test_tipo_incorreto_recusado(cliente, tipo):
    assert cliente.post('/api/chat', content='{}', headers={'Content-Type':tipo}).status_code == 415


def test_compressao_nao_aceita(cliente):
    assert cliente.post('/api/chat', json={'texto':'prova'}, headers={'Content-Encoding':'gzip'}).status_code == 415


def test_query_desconhecida_duplicada_e_cookie_forjado(cliente):
    assert cliente.get('/api/health?admin=true').status_code == 422
    entrar(cliente)
    assert cliente.post('/api/admin/documentos?nome=a.txt&nome=b.txt&publico=true', content=b'prova').status_code == 422
    cliente.cookies.clear()
    cliente.cookies.set('consultor', 'admin=true')
    assert cliente.get('/api/admin/documentos').status_code == 401
    assert cliente.delete('/api/admin/documentos/1').status_code == 401


@pytest.mark.parametrize('headers', [[(b'host',b'a'),(b'host',b'a')],
    [(b'content-length',b'2'),(b'transfer-encoding',b'chunked')],
    [(b'content-length',b'-1')],[(b'content-length',b'1'),(b'Content-Length',b'2')],
    [(b'transfer-encoding',b'chunked'),(b'transfer-encoding',b'chunked')],
    [(b'transfer-encoding',b'gzip')],[(b'cookie',b'a=1'),(b'cookie',b'a=2')]])
def test_cabecalhos_ambiguos(headers):
    with pytest.raises(HTTPException) as captura:
        cabecalhos({'headers':headers})
    assert captura.value.status_code == 400


def test_cabecalhos_e_url_limitados():
    with pytest.raises(HTTPException) as captura:
        cabecalhos({'headers':[(b'a', b'x'*16385)]})
    assert captura.value.status_code == 431
    with pytest.raises(HTTPException) as captura:
        preparar({'headers':[], 'query_string':b'x'*4097, 'path':'/', 'method':'GET'})
    assert captura.value.status_code == 414


def test_limite_real_de_bytes_sem_content_length():
    async def bloco():
        return {'type':'http.request', 'body':b'x'*8193}
    with pytest.raises(HTTPException) as captura:
        asyncio.run(ler_json(LeitorLimitado(bloco, 8192, 1)))
    assert captura.value.status_code == 413


def test_corpo_lento_expira_e_desconexao_nao_e_json():
    async def lento():
        await asyncio.sleep(1)
    with pytest.raises(HTTPException) as captura:
        asyncio.run(ler_json(LeitorLimitado(lento, 8192, 0.001)))
    assert captura.value.status_code == 408
    async def desconectado():
        return {'type':'http.disconnect'}
    with pytest.raises(HTTPException) as captura:
        asyncio.run(ler_json(LeitorLimitado(desconectado, 8192, 1)))
    assert captura.value.status_code == 400


def test_capacidade_global_limitada_e_liberada():
    trafego = ControleTrafego()
    for i in range(24):
        trafego.entrar(str(i))
    with pytest.raises(HTTPException) as captura:
        trafego.entrar('novo')
    assert captura.value.status_code == 503
    trafego.sair()
    trafego.entrar('novo')
    for _ in range(24):
        trafego.sair()


def test_429_inclui_rotas_inexistentes(cliente):
    for _ in range(119):
        assert cliente.get('/inexistente').status_code == 404
    resposta = cliente.get('/inexistente')  # Fixture já abriu uma sessão.
    assert resposta.status_code == 429 and resposta.headers['Retry-After'] == '60'


@pytest.mark.parametrize('valor', ['*','0.0.0.0','192.0.2.1','127.0.0.0/8','localhost'])
def test_proxy_nunca_confia_em_qualquer_remetente(valor):
    with pytest.raises(ValueError):
        proxies_confiaveis(valor)


def test_opcoes_servidor_compativeis(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXIES','127.0.0.1')
    monkeypatch.delenv('APP_PORT', raising=False)
    opcoes = opcoes_uvicorn('https://dominio.invalid')
    assert opcoes['port'] == 8000 and opcoes['host'] == '127.0.0.1'
    assert set(opcoes) <= set(inspect.signature(uvicorn.run).parameters)
    assert opcoes['proxy_headers'] and opcoes['forwarded_allow_ips'] == '127.0.0.1'
