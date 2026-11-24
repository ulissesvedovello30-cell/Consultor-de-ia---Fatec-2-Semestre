"""Regressões dos erros reais encontrados na auditoria de QA, DBA e arquitetura."""
import asyncio
import json
from pathlib import Path
import pytest
from aplicacao.core.chatbot import Chatbot
from aplicacao.dominio.erros import ErroBancoDeDados
from aplicacao.dominio.metadados import Metadados
from aplicacao.dominio.trecho_documento import TrechoDocumento
from aplicacao.infra.gemini.gemini_http import ErroCotaGemini
from aplicacao.infra.persistencia.sqlite import abrir_sqlite, checkpoint_wal
from aplicacao.infra.repositorios.indice_textual import migrar_publicados
from aplicacao.infra.repositorios.repositorio_trechos import RepositorioTrechos
from aplicacao.servicos.acervo.base_textual import BaseTextual, MODELO_TEXTUAL
from aplicacao.servicos.gemini.gemini import juntar_partes
from aplicacao.servicos.recuperacao.filtros_acervo import delimitar
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta
from aplicacao.servicos.respostas.consultor_rag import ConsultorRAG
from aplicacao.servicos.respostas.politica import validar_pergunta, validar_documento, EntradaRecusada
from aplicacao.servicos.respostas.respostas_rag import interpretar
from aplicacao.web.configuracao import ConfigWeb

RAIZ = Path(__file__).resolve().parents[2]


class _SeletorN:
    def __init__(self, n=1):
        self.n = n

    def gerar(self, mensagens):
        qtd = mensagens[1]['content'].count('[Trecho ')
        if not qtd:
            return json.dumps({'status': 'insuficiente', 'trechos': []})
        return json.dumps({'status': 'respondida', 'trechos': list(range(1, min(self.n, qtd) + 1))})


def test_isbn_no_ppc_esg_nao_e_confundido_com_telefone_em_upload():
    from aplicacao.seguranca.documentos.extracao import extrair_protegido
    paginas = extrair_protegido(RAIZ / 'documentos/cursos/esg/PPC-CST-ESG.pdf')
    for _, texto in paginas:
        validar_documento(texto)
    with pytest.raises(EntradaRecusada):
        validar_pergunta('Meu telefone é (19) 99999-1234')
    with pytest.raises(EntradaRecusada):
        validar_pergunta('Contato 19 3522-1234')
    with pytest.raises(EntradaRecusada):
        validar_pergunta('Celular 11987654321')


def test_evento_publicado_fora_do_calendario_mensal_e_encontrado(tmp_path):
    engine = abrir_sqlite(str(tmp_path / 'acervo.db'))
    try:
        base = BaseTextual(RepositorioTrechos(engine))
        aviso = tmp_path / 'aviso_evento.txt'
        aviso.write_text('Aviso oficial: O evento Semana da Inovacao acontece em 30 de novembro de 2026.', encoding='utf-8')
        base.indexar_arquivo(aviso, forcar=True)
        trechos = base.buscar('Quando é o evento Semana da Inovação?', 8)
        assert any('30 de novembro de 2026' in t.texto for t in trechos)
    finally:
        checkpoint_wal(engine)
        engine.dispose()


def test_upload_com_nome_completo_do_curso_e_encontrado(tmp_path):
    engine = abrir_sqlite(str(tmp_path / 'acervo.db'))
    try:
        base = BaseTextual(RepositorioTrechos(engine))
        ppc = tmp_path / 'ppc_ia.txt'
        ppc.write_text('3.1 Identificação\nO CST em Inteligência Artificial é Experimental.', encoding='utf-8')
        reg = tmp_path / 'reg_tcc.txt'
        reg.write_text('Regulamento de TCC: A entrega do TCC ocorre na penultima semana letiva.', encoding='utf-8')
        base.indexar_arquivo(ppc, forcar=True, metadados=Metadados(curso='IA'))
        base.indexar_arquivo(reg, forcar=True, metadados=Metadados(curso='Inteligência Artificial'))
        for pergunta in ('Qual o prazo de entrega do TCC de Inteligência Artificial?', 'Qual o prazo de entrega do TCC de IA?'):
            trechos = base.buscar(pergunta, 8)
            filtrados, pendentes = delimitar(pergunta, trechos)
            assert not pendentes
            assert any('penultima semana letiva' in t.texto for t in filtrados)
    finally:
        engine.dispose()


@pytest.mark.parametrize('palavra', ['grande', 'pegar', 'prato', 'provar', 'justo', 'justa', 'susto', 'tacas', 'pagas'])
def test_palavras_comuns_nao_sao_corrompidas_pelo_corretor(palavra):
    assert preparar_consulta(palavra) == palavra


@pytest.mark.parametrize('pergunta,esperado', [
    ('O curso de tecnologia é gratuito?', 'gratuitos'),
    ('Qual a grade de matérias?', '/ia/'),
    ('Qual a mensalidade em 2026?', 'gratuitos'),
    ('Qual o horário das aulas em 2026?', '7h40'),
])
def test_perguntas_validas_da_fatec_nao_caem_em_curso_desconhecido(base_pdf, pergunta, esperado):
    bot = Chatbot(ConsultorRAG(base_pdf, _SeletorN(1), limiar_similaridade=base_pdf.limiar_relevancia))
    resposta = asyncio.run(bot.processar_mensagem('faq-valido', pergunta))
    assert resposta.sucesso and esperado in resposta.texto


@pytest.mark.parametrize('pergunta', [
    'Qual a carga horária total?',
    'Como faço transferência externa?',
    'O que é trancamento?',
    'Qual a frequência mínima para aprovação?',
    'Como funciona o aproveitamento de estudos?',
    'Tem monitoria ou iniciação científica?',
])
def test_escopo_aceita_perguntas_academicas_legitimas(pergunta):
    assert validar_pergunta(pergunta) == pergunta


def test_followup_horario_disso_nao_responde_horario_das_aulas(base_pdf):
    bot = Chatbot(ConsultorRAG(base_pdf, _SeletorN(1), limiar_similaridade=base_pdf.limiar_relevancia))
    r1 = asyncio.run(bot.processar_mensagem('hack', 'Quando é o Hackathon?'))
    assert r1.sucesso and '27 e 28 de março de 2026' in r1.texto
    r2 = asyncio.run(bot.processar_mensagem('hack', 'Qual o horário disso?'))
    assert '7h40' not in r2.texto and '19h às 22h30' not in r2.texto


def test_nova_pergunta_adicionada_na_faq_e_recuperada_sem_marcadores(tmp_path):
    engine = abrir_sqlite(str(tmp_path / 'faq.db'))
    try:
        base = BaseTextual(RepositorioTrechos(engine))
        faq = tmp_path / 'FAQ_secretaria.txt'
        faq.write_text(
            'Assunto: biblioteca\n'
            'Pergunta: Qual o horário da biblioteca?\n'
            'Resposta: A biblioteca funciona das 8h às 21h.\n',
            encoding='utf-8',
        )
        base.indexar_arquivo(faq, forcar=True)
        trechos = base.buscar('Qual o horário da biblioteca?', 5)
        assert trechos and trechos[0].texto == 'A biblioteca funciona das 8h às 21h.'
        assert 'Assunto:' not in trechos[0].texto
    finally:
        engine.dispose()


def test_selecao_valida_com_4_trechos_longos_nao_e_descartada():
    usados = [TrechoDocumento('ppc.pdf', i, f'Trecho {i} ' + 'x' * 850, similaridade=0.9) for i in range(1, 5)]
    resp = interpretar(json.dumps({'status': 'respondida', 'trechos': [1, 2, 3, 4]}), usados, 0.9)
    assert resp.encontrou and len(resp.fontes) == 4


def test_novo_curso_publicado_aparece_no_catalogo(tmp_path):
    engine = abrir_sqlite(str(tmp_path / 'cursos.db'))
    try:
        base = BaseTextual(RepositorioTrechos(engine))
        ads = tmp_path / 'PPC_ADS.txt'
        ads.write_text('3.1 Identificação\nO CST em Análise e Desenvolvimento de Sistemas é um curso regular da Fatec.', encoding='utf-8')
        base.indexar_arquivo(ads, forcar=True, metadados=Metadados(curso='ADS'))
        trechos = base.buscar('Quais cursos a Fatec oferece?', 8)
        assert any('Análise e Desenvolvimento de Sistemas' in t.texto for t in trechos)
    finally:
        engine.dispose()


def test_indices_wal_e_protecao_migracao_sqlite(tmp_path):
    db = tmp_path / 'acervo.sqlite3'
    engine = abrir_sqlite(str(db))
    try:
        repo = RepositorioTrechos(engine)
        base = BaseTextual(repo)
        doc = tmp_path / 'a.txt'
        doc.write_text('Calendario oficial da Fatec Rio Claro.', encoding='utf-8')
        base.indexar_arquivo(doc, forcar=True)
        with engine.connect() as c:
            indices = {r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='index'")}
        assert 'ix_rag_documento_versao_ativa' in indices
        assert 'ix_rag_versao_modelo_vigencia' in indices
        with pytest.raises(ValueError):
            migrar_publicados(engine, 'gemini-embedding-001:768:retrieval:v1')
        with pytest.raises(ErroBancoDeDados):
            repo.carregar(MODELO_TEXTUAL)
        checkpoint_wal(engine)
    finally:
        engine.dispose()
    assert db.stat().st_size > 4096


def test_config_vazia_juntar_partes_cota_busca_e_trecho_pii(monkeypatch):
    monkeypatch.setenv('SEGURANCA_DB', '')
    assert ConfigWeb.ambiente().seguranca_db.endswith('seguranca.sqlite3')
    assert juntar_partes([{'thought': True, 'text': 'x'}, {'thoughtSignature': 'y'}, {'text': 'ok'}]) == 'ok'

    class _BaseCota:
        def buscar(self, pergunta, k):
            raise ErroCotaGemini('429')

    bot_cota = Chatbot(ConsultorRAG(_BaseCota(), _SeletorN(1)))
    assert asyncio.run(bot_cota.processar_mensagem('c1', 'Quando é a prova?')).estado == 'cota'

    class _BasePII:
        def buscar(self, pergunta, k):
            return [
                TrechoDocumento('m.txt', 1, 'CPF: original obrigatorio.', similaridade=0.95),
                TrechoDocumento('m.txt', 2, 'A matricula ocorre na secretaria.', similaridade=0.9),
            ]

    bot_pii = Chatbot(ConsultorRAG(_BasePII(), _SeletorN(1), limiar_similaridade=0.5))
    resp = asyncio.run(bot_pii.processar_mensagem('c2', 'Como funciona a matricula?'))
    assert resp.sucesso and 'secretaria' in resp.texto
