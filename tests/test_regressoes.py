import asyncio
import threading
import time
from datetime import date
import numpy as np
import pytest
from sqlalchemy import create_engine, select, func
from infra.esquema import metadata, versoes
from infra.repositorio_trechos import RepositorioTrechos, identidade
from servicos.base_conhecimento import BaseConhecimento
from servicos.demo_offline import EmbeddingsLexicais
from servicos.executor_rag import ExecutorRAG
from dominio.erros import ErroPrazo, ErroOcupado, ErroIndexacao
from dominio.metadados import Metadados


@pytest.fixture
def acervo(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'base.db'))
    metadata.create_all(engine)
    yield engine, BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    engine.dispose()


def test_atualizacao_em_outro_processo_e_exclusao_ficam_visiveis(acervo, tmp_path):
    engine, base = acervo
    outra = BaseConhecimento(RepositorioTrechos(engine), EmbeddingsLexicais())
    arquivo = tmp_path / 'provas.txt'
    arquivo.write_text('Prova de Banco de Dados dia 10.', encoding='utf-8')
    base.indexar_arquivo(arquivo)
    assert 'dia 10' in outra.buscar('prova')[0].texto
    arquivo.write_text('Prova de Banco de Dados dia 20.', encoding='utf-8')
    base.indexar_arquivo(arquivo)
    assert [t.texto for t in outra.buscar('prova')] == ['Prova de Banco de Dados dia 20.']
    base.repositorio.excluir(identidade(arquivo.name))
    assert outra.buscar('prova') == []


def test_mesmo_conteudo_nomes_diferentes_e_versoes_antigas_apagadas(acervo, tmp_path):
    engine, base = acervo
    for nome in ['a.txt', 'b.txt']:
        path = tmp_path / nome
        path.write_text('Prova dia 10.')
        assert base.indexar_arquivo(path) == 1
    path.write_text('Prova dia 20.')
    base.indexar_arquivo(path)
    assert len(base.repositorio.listar()) == 2
    with engine.connect() as conexao:
        assert conexao.scalar(select(func.count()).select_from(versoes)) == 2


def test_falha_embedding_nao_altera_versao_ativa(acervo, tmp_path, monkeypatch):
    engine, base = acervo
    path = tmp_path / 'a.txt'
    path.write_text('Prova dia 10.')
    base.indexar_arquivo(path)
    path.write_text('Prova dia 20.')
    def falhar(*args):
        raise RuntimeError('embedding falhou')
    monkeypatch.setattr(base._embedder, 'codificar', falhar)
    with pytest.raises(RuntimeError):
        base.indexar_arquivo(path)
    assert base.repositorio.carregar(base._modelo_embedding)[0][0].texto == 'Prova dia 10.'


def test_pdf_parcial_recusado_sem_sucesso_falso(tmp_path):
    from pypdf import PdfWriter
    from servicos.processador_documento import extrair_paginas
    caminho = tmp_path / 'scan.pdf'
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.write(caminho)
    with pytest.raises(ErroIndexacao, match='OCR'):
        extrair_paginas(caminho)


def test_timeout_preserva_vaga_ate_thread_acabar():
    liberacao = threading.Event()
    executor = ExecutorRAG(prazo=0.03, capacidade=1)
    def demorar(prazo_final):
        liberacao.wait(1)
    async def fluxo():
        with pytest.raises(ErroPrazo):
            await executor.executar(demorar)
        with pytest.raises(ErroOcupado):
            await executor.executar(demorar)
        liberacao.set()
    asyncio.run(fluxo())


def test_cancelamento_http_nao_libera_thread_precocemente():
    comecou, liberacao = threading.Event(), threading.Event()
    executor = ExecutorRAG(prazo=1, capacidade=1)
    def demorar(prazo_final):
        comecou.set()
        liberacao.wait(2)
    async def fluxo():
        tarefa = asyncio.create_task(executor.executar(demorar))
        await asyncio.to_thread(comecou.wait, 1)
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa
        with pytest.raises(ErroOcupado):
            await executor.executar(demorar)
        liberacao.set()
    asyncio.run(fluxo())


def test_pergunta_atual_nao_desaparece_no_contexto():
    from core.chatbot import Chatbot
    bot = Chatbot(None)
    bot._ultima_pergunta['x'] = (time.monotonic(), 'a' * 1500)
    atual = 'isso ' + 'b' * 1400 + ' quando é a prova?'
    contexto = bot._com_contexto('x', atual)
    assert atual in contexto and len(contexto) <= 2100


def test_limite_de_chaves_nao_cresce_sem_controle():
    from core.limitador import LimitadorTaxa
    limitador = LimitadorTaxa(10, 60)
    limitador._LIMITE_DE_CHAVES = 2
    assert limitador.permitir('a') and limitador.permitir('b')
    assert not limitador.permitir('c')
    assert len(limitador._eventos) == 2



def test_ambiguidades_pedem_esclarecimento_e_filtro_exclui_outro_curso():
    from dominio.trecho_documento import TrechoDocumento
    from servicos.filtros_acervo import delimitar
    trechos = [TrechoDocumento('a', None, 'dia 10', curso='DSM', ano=2026),
               TrechoDocumento('b', None, 'dia 20', curso='Gestão', ano=2026)]
    _, pendentes = delimitar('Quando é a prova?', trechos)
    assert pendentes and 'curso' in pendentes[0]
    encontrados, pendentes = delimitar('Quando é a prova de gestao?', trechos)
    assert len(encontrados) == 1 and encontrados[0].curso == 'Gestão' and not pendentes


def test_migracao_recusa_versoes_legadas_conflitantes():
    from types import SimpleNamespace
    from infra.legado import agrupar
    linhas = [SimpleNamespace(arquivo='a.pdf', hash_arquivo=h) for h in ['velho', 'novo']]
    with pytest.raises(ErroIndexacao, match='conflitantes'):
        agrupar(linhas)


def test_fila_inclui_tempo_esperando():
    executor = ExecutorRAG(prazo=0.05, capacidade=2)
    executadas = []
    def lento(prazo_final):
        executadas.append(1)
        time.sleep(0.12)
    async def fluxo():
        retornos = await asyncio.gather(executor.executar(lento), executor.executar(lento), return_exceptions=True)
        assert all(isinstance(r, ErroPrazo) for r in retornos)
    asyncio.run(fluxo())
    assert len(executadas) == 1


def test_sessao_admin_expira_mesmo_com_cookie_valido():
    from web.sessoes import Sessoes
    agora = [10]
    sessoes = Sessoes(ttl=60, relogio=lambda: agora[0])
    token, sessao = sessoes.criar()
    assert sessoes.obter(token) is sessao
    agora[0] = 71
    assert sessoes.obter(token) is None
