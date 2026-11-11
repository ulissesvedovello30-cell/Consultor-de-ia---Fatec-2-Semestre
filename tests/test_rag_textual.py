"""Inicialização, recuperação textual e painel com a API de embeddings bloqueada."""
import asyncio
import json
import re
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text
import config
import montagem
from dominio.metadados import Metadados
from infra.gemini_http import ClienteGemini
from infra.repositorio_trechos import identidade
from servicos.base_textual import BaseTextual
from seguranca.totp import codigo
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash


class RAGTextual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = TemporaryDirectory()
        cls.metodos = []
        cls.chamadas = []
        cls.remoto = None
        cls.falha = False
        cls.patches = [patch.object(config, 'BUSCA_ACERVO', 'textual'),
            patch.object(config, 'SQLITE_CAMINHO', str(Path(cls.pasta.name)/'acervo.db')),
            patch.object(config, 'GEMINI_API_KEY', 'chave-somente-teste'),
            patch.object(montagem, 'ClienteGemini', cls.cliente)]
        for p in cls.patches: p.start()
        with montagem.abrir_chatbot() as (_, base):
            cls.numero = base.total_trechos
            assert cls.metodos == []
            assert len(base.repositorio.listar()) == 3

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patches): p.stop()
        cls.pasta.cleanup()

    @classmethod
    def cliente(cls, chave):
        return ClienteGemini(chave, httpx.MockTransport(cls.receber))

    @classmethod
    def receber(cls, req):
        metodo = req.url.path.split(':')[-1]
        cls.metodos.append(metodo)
        assert metodo == 'generateContent', 'Embeddings não devem ser usados no RAG textual.'
        if cls.falha:
            return httpx.Response(429, json={'error': {'details': [{'violations':
                [{'quotaId': 'GenerateRequestsPerDayPerProject', 'quotaValue': '20'}]}]}})
        mensagem = json.loads(req.content)['contents'][0]['parts'][0]['text']
        trecho = re.search(r'\[Trecho 1 \| Fonte: [^\n]+\]\n(.*?)(?:\n\n---\n\n|\n\nPERGUNTA:)', mensagem, re.S)[1]
        resposta = json.dumps({'status': 'respondida', 'afirmacoes': [{'texto': trecho, 'fontes': [1]}]})
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': resposta}]}}]})

    def test_01_acervo_real_e_fontes_recuperadas(self):
        self.assertEqual(self.numero, 1039)
        with montagem.abrir_chatbot() as (_, base):
            casos = [('Qual a mensalidade?', 'gratuitos'), ('Qual o horário de IA?', '7h40'),
                     ('Quanto tempo dura o curso?', '2 anos'), ('As aulas são presenciais?', 'presencial')]
            for pergunta, esperado in casos:
                candidatos = base.buscar(pergunta)
                self.assertTrue(candidatos, pergunta)
                texto = candidatos[0].texto.lower()
                self.assertIn(esperado, texto)
                self.assertEqual(candidatos[0].arquivo, 'FAQ_secretaria.txt')
            self.assertFalse(base.buscar('abacaxi intergalatico azul'))
            for t in base.buscar('Qual a carga horária de Inteligência Artificial?'):
                self.assertNotEqual(t.curso, 'ESG')

    def test_02_resposta_chama_somente_geracao(self):
        with montagem.abrir_chatbot() as (bot, base):
            n = len(self.metodos)
            resposta = asyncio.run(bot.processar_mensagem('teste', 'Qual a mensalidade?'))
            self.assertTrue(resposta.sucesso)
            self.assertIn('gratuitos', resposta.texto)
            self.assertEqual(self.metodos[n:], ['generateContent'])
            self.assertTrue(resposta.fontes)

    def test_03_reinicio_preserva_documentos_e_conclui_fts(self):
        with montagem.abrir_chatbot() as (_, base):
            self.assertEqual(base.total_trechos, 1039)
            with base.repositorio._engine.connect() as c:
                self.assertEqual(c.scalar(text("SELECT count(*) FROM rag_inicializacao WHERE chave='acervo_inicial_fts5_v1'")), 1)
                self.assertEqual(c.scalar(text("SELECT count(*) FROM rag_trecho WHERE length(embedding)<>0")), 0)

    def test_04_painel_upload_substituir_excluir(self):
        secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        cfg = ConfigWeb(origem='http://testserver', usuario='admin',
            senha_hash=gerar_hash('senha-de-teste-12345'), totp_segredo=secret,
            seguranca_db=str(Path(self.pasta.name)/'seguranca.db'))
        with TestClient(criar_app(configuracao=cfg)) as c:
            self.assertEqual(c.get('/').status_code, 200)
            self.assertTrue(c.get('/api/health').json()['pronto'])
            c.headers['X-CSRF-Token'] = c.get('/api/sessao').json()['csrf']
            r = c.post('/api/chat', json={'texto': 'Qual a mensalidade?'})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()['sucesso'])
            c.app.state.protecao_login.relogio = lambda: 1234567890
            login = c.post('/api/admin/login', json={'usuario': 'admin',
                'senha': 'senha-de-teste-12345', 'otp': codigo(secret, 1234567890//30)})
            self.assertEqual(login.status_code, 200)
            c.headers['X-CSRF-Token'] = login.json()['csrf']
            url = '/api/admin/documentos'
            params = {'nome': 'publicacao.txt', 'publico': 'true'}
            self.assertEqual(c.post(url, params=params, content=b'A biblioteca abre aos sabados.').status_code, 200)
            doc = next(d for d in c.get(url).json() if d['nome']=='publicacao.txt')
            antigo = f"/api/fontes/{doc['documento_id']}/{doc['id_1']}"
            self.assertIn('sabados', c.get(antigo).text)
            self.assertEqual(c.post(url, params=params, content=b'A biblioteca abre aos domingos.').status_code, 200)
            self.assertEqual(c.get(antigo).status_code, 404)
            self.assertEqual(c.delete(url+'/'+doc['documento_id']).status_code, 200)
            self.assertFalse(any(t.arquivo=='publicacao.txt' for t in c.app.state.base.buscar('biblioteca sabados domingos')))

    def test_05_cota_de_geracao_nao_impede_inicio(self):
        type(self).falha = True
        try:
            with montagem.abrir_chatbot() as (bot, base):
                self.assertEqual(base.total_trechos, 1039)
                r = asyncio.run(bot.processar_mensagem('cota', 'Qual a mensalidade?'))
                self.assertEqual(r.estado, 'indisponivel')
        finally:
            type(self).falha = False

    def test_06_fts_escape_vigencia_e_transacao(self):
        with montagem.abrir_chatbot() as (_, base):
            for q in ['" OR 1=1 --', 'NEAR("a", "b")', '***', ''] :
                base.buscar(q)
            p = Path(self.pasta.name)/'transacao.txt'
            p.write_text('A secretaria funciona em horario vespertino.')
            base.indexar_arquivo(p, metadados=Metadados(inicio=__import__('datetime').date(2099,1,1)))
            self.assertFalse(any(t.arquivo == p.name for t in base.buscar('secretaria vespertino')))
            base.repositorio.excluir(identidade(p.name))


    def test_07_migracao_do_banco_vetorial_sem_novas_chamadas(self):
        from infra.sqlite import abrir_sqlite
        from infra.repositorio_trechos import RepositorioTrechos
        from infra.inicializacao import registrar_carga
        from dominio.trecho_documento import TrechoDocumento
        import numpy as np
        banco = str(Path(self.pasta.name)/'legado.db')
        engine = abrir_sqlite(banco)
        repo = RepositorioTrechos(engine)
        repo.substituir_arquivo('hash-legado', 'gemini-embedding-001:768:retrieval:v1',
            [TrechoDocumento('legado.txt', None, 'O estacionamento fica na entrada lateral.')],
            np.array([[1]+[0]*767], dtype=np.float32))
        registrar_carga(engine)
        engine.dispose()
        antes = len(self.metodos)
        with patch.object(config, 'SQLITE_CAMINHO', banco), montagem.abrir_chatbot() as (_, base):
            self.assertEqual(len(base.repositorio.listar()), 4)
            self.assertEqual(base.buscar('estacionamento entrada lateral')[0].arquivo, 'legado.txt')
        self.assertEqual(len(self.metodos), antes)


    def test_08_falha_na_substituicao_preserva_texto_e_fts(self):
        from sqlalchemy.exc import SQLAlchemyError
        from dominio.erros import ErroBancoDeDados
        with montagem.abrir_chatbot() as (_, base):
            p = Path(self.pasta.name)/'atomicidade.txt'
            p.write_text('O estacionamento fica na entrada lateral.')
            base.indexar_arquivo(p)
            original = base.repositorio._gravar
            def falhar(*args):
                original(*args)
                raise SQLAlchemyError('falha simulada depois de gravar')
            p.write_text('O estacionamento fica no portao dos fundos.')
            with patch.object(base.repositorio, '_gravar', side_effect=falhar):
                with self.assertRaises(ErroBancoDeDados):
                    base.indexar_arquivo(p, forcar=True)
            fontes = [t for t in base.buscar('estacionamento entrada lateral') if t.arquivo==p.name]
            self.assertIn('entrada lateral', fontes[0].texto)
            self.assertFalse(any(t.arquivo==p.name for t in base.buscar('portao fundos')))
            base.repositorio.excluir(identidade(p.name))


    def test_09_exclusao_nao_e_desfeita_no_reinicio(self):
        with montagem.abrir_chatbot() as (_, base):
            base.repositorio.excluir(identidade('FAQ_secretaria.txt'))
        antes = len(self.metodos)
        with montagem.abrir_chatbot() as (_, base):
            self.assertNotIn('FAQ_secretaria.txt', [d['nome'] for d in base.repositorio.listar()])
        self.assertEqual(len(self.metodos), antes)
