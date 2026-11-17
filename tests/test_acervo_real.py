"""Integração das fontes recebidas, autenticação local e túnel opcional."""
import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import httpx
import numpy as np
import pytest
from sqlalchemy import create_engine, select, func
from fastapi.testclient import TestClient
from tests.apoio_acervo import montar_acervo_teste
from dominio.erros import ErroIndexacao
from dominio.trecho_documento import TrechoDocumento
from infra.esquema import documentos, versoes, trechos, metadata
from infra.gemini_http import ClienteGemini, ErroGemini
from infra.tunel_ngrok import escolher_tunel, parametros
from servicos.gemini import EmbeddingsGemini
from servicos.documentos_reais import manifesto, retirar_exemplos, preparar_paginas, conferir_documento
from servicos.acervo_institucional import carregar_iniciais, DADOS
from servicos.politica import PESSOAIS
from servicos.filtros_acervo import delimitar
from seguranca.identidade_admin import validar_email
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash


@pytest.fixture(scope='module')
def acervo_real(tmp_path_factory):
    pasta=tmp_path_factory.mktemp('acervo-real')
    engine=create_engine('sqlite:///'+str(pasta/'acervo.db'),connect_args={'check_same_thread':False})
    bot,base=montar_acervo_teste(engine)
    yield bot,base,pasta
    engine.dispose()


def test_fontes_reais_extraidas_com_pagina_e_minimizacao(acervo_real):
    _,base,_=acervo_real
    fontes=base.repositorio.listar()
    assert {f['nome'] for f in fontes}=={f['arquivo'] for f in manifesto()['fontes']}
    ativos,_=base.repositorio.carregar(base._modelo_embedding)
    assert all(not PESSOAIS.search(t.texto) for t in ativos)
    assert any(t.arquivo=='PPC-CST-ESG.pdf' and t.pagina==26 and '1.600' in t.texto for t in ativos)
    assert any(t.arquivo=='PPC_IA_RioClaro_2025_1.pdf' and t.pagina==26 and '2.000' in t.texto for t in ativos)
    assert all(len(t.texto)<=1000 for t in ativos)


def test_carga_repetida_nao_reenvia_textos_ao_provedor(acervo_real,monkeypatch):
    _,base,_=acervo_real
    def proibido(textos):
        raise AssertionError('Carga idêntica não deve chamar embeddings')
    monkeypatch.setattr(base._embedder,'codificar',proibido)
    assert set(carregar_iniciais(base).values())=={0}


@pytest.mark.parametrize('pergunta,esperado',[
 ('Quais cursos a Fatec oferece?','Inteligência Artificial'),
 ('Qual a mensalidade?','gratuitos'),
 ('Qual horário dos cursos?','7h40'),
 ('As aulas são presenciais?','presencialmente'),
 ('Qual o período para inscrições no Vestibular?','não informa datas'),
 ('Como consigo acessar a grade curricular de cada curso?','https://fatecrioclaro.cps.sp.gov.br/esg/'),
 ('Quanto tempo de duração é o curso?','2 anos'),
 ('Os cursos são considerados de nível superior ou técnico?','nível superior'),
])
def test_faq_respondida_com_fonte_ativa(acervo_real,pergunta,esperado):
    bot,_,_=acervo_real
    resposta=asyncio.run(bot.processar_mensagem(pergunta,pergunta))
    assert resposta.sucesso, resposta.texto
    assert esperado in resposta.texto
    assert resposta.fontes and resposta.fontes[0].arquivo=='FAQ_secretaria.txt'


def test_exclusao_da_faq_nao_deixa_resposta_em_cache(acervo_real):
    _,base,_=acervo_real
    from servicos.faq import localizar
    from infra.repositorio_trechos import identidade
    base.repositorio.excluir(identidade('FAQ_secretaria.txt'))
    resultado=base.buscar('Qual a mensalidade?')
    assert not localizar('Qual a mensalidade?',resultado)
    carregar_iniciais(base)


def test_nome_original_sem_hash_nao_libera_dados_pessoais(tmp_path):
    arquivo=tmp_path/'PPC-CST-ESG.pdf'
    arquivo.write_bytes(b'arquivo adulterado')
    paginas=[(1,'CPF: 123.456.789-00')]
    assert preparar_paginas(arquivo,paginas)==paginas


def test_limpeza_remove_so_hashes_ficticios(acervo_real):
    _,base,_=acervo_real
    repo=base.repositorio
    fake=TrechoDocumento('exemplo-renomeado.txt',None,'Exemplo para retirada')
    repo.substituir_arquivo(manifesto()['hashes_ficticios_removidos'][0],base._modelo_embedding,[fake],np.ones((1,1024)))
    assert retirar_exemplos(repo)==1
    assert len(repo.listar())==3
    assert retirar_exemplos(repo)==0
    with pytest.raises(ErroIndexacao):
        conferir_documento(manifesto()['hashes_ficticios_removidos'][1])


def test_nome_completo_delimita_ia():
    fontes=[TrechoDocumento('a',26,'A',curso='IA'),TrechoDocumento('b',26,'B',curso='ESG')]
    encontrados,pendentes=delimitar('Qual a carga horária de Inteligência Artificial?',fontes)
    assert [t.curso for t in encontrados]==['IA'] and not pendentes


def test_gmail_login_upload_e_consulta_publica(acervo_real,tmp_path):
    bot,base,_=acervo_real
    @contextmanager
    def fabrica():
        yield bot,base
    senha='senha-local-para-teste-001'
    cfg=ConfigWeb(origem='http://testserver',usuario='conta.teste@gmail.com',senha_hash=gerar_hash(senha),seguranca_db=str(tmp_path/'seg.db'))
    with TestClient(criar_app(fabrica,cfg,'teste')) as c:
        csrf=c.get('/api/sessao').json()['csrf'];c.headers['X-CSRF-Token']=csrf
        assert c.get('/api/admin/documentos').status_code==401
        r=c.post('/api/chat',json={'texto':'As aulas são presenciais?'})
        assert r.status_code==200 and r.json()['sucesso']
        assert c.post('/api/admin/login',json={'usuario':cfg.usuario,'senha':'senha errada'}).status_code==401
        assert c.post('/api/admin/login',json={'usuario':'outra@gmail.com','senha':senha}).status_code==401
        r=c.post('/api/admin/login',json={'usuario':' CONTA.TESTE@GMAIL.COM ','senha':senha})
        assert r.status_code==200,r.text
        c.headers['X-CSRF-Token']=r.json()['csrf']
        params={'nome':'FAQ_secretaria.txt','publico':'true'}
        r=c.post('/api/admin/documentos',params=params,content=(DADOS/'FAQ_secretaria.txt').read_bytes())
        assert r.status_code==200,r.text
        assert len(c.get('/api/admin/documentos').json())==3
        c.post('/api/admin/logout')
        assert c.get('/api/admin/documentos').status_code==401


@pytest.mark.parametrize('valor',['','sem-arroba','x@','x @gmail.com','x@gmail.com\nBcc:outra'])
def test_configurador_recusa_email_invalido(valor):
    with pytest.raises(ValueError): validar_email(valor)


def test_configurador_aceita_gmail_sem_exigir_conta_google():
    assert validar_email(' CONTA.TESTE@gmail.com ' )=='conta.teste@gmail.com'


def test_ngrok_desligado_nao_conecta(monkeypatch):
    import infra.tunel_ngrok as modulo
    monkeypatch.setattr(modulo,'conectar',lambda *a:pytest.fail('Não deve abrir rede'))
    cfg=ConfigWeb()
    with escolher_tunel(False,cfg) as efetiva: assert efetiva is cfg


def test_ngrok_exige_token_senha_e_totp(monkeypatch):
    cfg=ConfigWeb()
    monkeypatch.delenv('NGROK_AUTHTOKEN',raising=False)
    with pytest.raises(ValueError): parametros(cfg)
    monkeypatch.setenv('NGROK_AUTHTOKEN','token-teste')
    cfg=replace(cfg,senha_hash='hash',totp_segredo='JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP')
    assert parametros(cfg)==('token-teste',8000)


def test_ngrok_origem_https_e_limpeza_apos_erro(monkeypatch):
    import infra.tunel_ngrok as modulo
    chamadas=[]
    api=SimpleNamespace(disconnect=lambda *a,**k:chamadas.append('disconnect'),kill=lambda **k:chamadas.append('kill'))
    monkeypatch.setattr(modulo,'parametros',lambda *a:('token',8000))
    monkeypatch.setattr(modulo,'conectar',lambda *a:(api,object(),SimpleNamespace(public_url='https://teste.ngrok-free.app')))
    with pytest.raises(RuntimeError):
        with escolher_tunel(True,ConfigWeb()) as cfg:
            assert cfg.seguro and cfg.origem=='https://teste.ngrok-free.app'
            raise RuntimeError('falha da aplicação')
    assert chamadas==['disconnect','kill']


def test_embeddings_lotes_preservam_ordem_e_limite():
    tamanhos=[]
    def atender(request):
        dados=json.loads(request.content)['requests'];tamanhos.append(len(dados))
        assert all(d['model']=='models/gemini-embedding-001' for d in dados)
        assert all(d['embedContentConfig']['autoTruncate'] is False for d in dados)
        return httpx.Response(200,json={'embeddings':[{'values':[int(d['content']['parts'][0]['text'])+1]+[1]*767} for d in dados]})
    api=ClienteGemini('teste',httpx.MockTransport(atender))
    try:
        matriz=EmbeddingsGemini(api,'gemini-embedding-001').codificar([str(i) for i in range(65)])
        assert tamanhos==[32,32,1] and matriz.shape==(65,768)
        assert np.all(np.diff(matriz[:,0])>0)
    finally: api.fechar()


@pytest.mark.parametrize('resposta',[{}, {'embeddings':[]}, {'embeddings':[{'values':[0]*768}]}])
def test_lote_invalido_nao_produz_matriz(resposta):
    api=ClienteGemini('teste',httpx.MockTransport(lambda r:httpx.Response(200,json=resposta)))
    try:
        with pytest.raises(ErroGemini): EmbeddingsGemini(api,'gemini-embedding-001').codificar(['texto'])
    finally: api.fechar()
