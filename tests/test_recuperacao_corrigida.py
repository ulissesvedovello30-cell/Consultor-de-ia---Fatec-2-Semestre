"""Regressões de recuperação e seleção de evidências com os documentos incluídos."""
import asyncio
import json
import httpx
import pytest
from core.chatbot import Chatbot
from dominio.trecho_documento import TrechoDocumento
from infra.repositorio_trechos import RepositorioTrechos
from infra.sqlite import abrir_sqlite
from infra.gemini_http import ClienteGemini, ErroGemini, repetir_geracao
from servicos.base_textual import BaseTextual
from servicos.consultor_rag import ConsultorRAG
from servicos.gemini import payload_geracao
from servicos.inicializar_acervo import preparar_primeira_carga
from servicos.respostas_rag import interpretar


@pytest.fixture(scope='module')
def base_real(tmp_path_factory):
    """Disponibilize os PPCs e a FAQ em um banco temporário, sem chamadas externas.

    Args:
        tmp_path_factory: Criador de diretórios temporários do pytest.

    Yields:
        BaseTextual: Busca sobre os mesmos documentos entregues no projeto.
    """
    engine = abrir_sqlite(str(tmp_path_factory.mktemp('acervo-real') / 'acervo.db'))
    try:
        base = BaseTextual(RepositorioTrechos(engine))
        preparar_primeira_carga(engine, base)
        yield base
    finally:
        engine.dispose()


@pytest.mark.parametrize('pergunta,esperado', [
    ('Vocês podem me informar quais cursos a Fatec oferece?', 'Inteligência Artificial'),
    ('Qual é a duração dos cursos oferecidos?', '2 anos'),
    ('Em que horário acontecem as aulas de IA?', '7h40'),
    ('Preciso saber se a faculdade cobra mensalidade.', 'gratuitos'),
    ('Quais são os horários dos cursos?', '19h'),
    ('Quais cursos?', 'Sustentabilidade'),
])
def test_parafrases_da_faq(base_real, pergunta, esperado):
    """Recupere a FAQ mesmo com flexões ou formas conversacionais na pergunta.

    Args:
        base_real: Acervo temporário com os documentos incluídos.
        pergunta (str): Variação que antes perdia cobertura ou prioridade.
        esperado (str): Informação presente na fonte real.
    """
    trechos = base_real.buscar(pergunta)
    assert trechos and trechos[0].arquivo == 'FAQ_secretaria.txt'
    assert esperado in trechos[0].texto
    assert trechos[0].similaridade >= base_real.limiar_relevancia


@pytest.mark.parametrize('pergunta,pagina,esperado', [
    ('Quais são os objetivos do curso de IA?', 30, 'formar profissionais'),
    ('Como funciona o trabalho de graduação de IA?', 87, '7.1 Trabalho de Graduação'),
    ('Quais são os requisitos para entrar no curso de ESG?', 30, 'processo seletivo'),
])
def test_prioridade_do_corpo_do_ppc(base_real, pergunta, pagina, esperado):
    """Prefira a seção que explica o assunto a sumários e menções genéricas.

    Args:
        base_real: Busca sobre os PDFs reais.
        pergunta (str): Assunto de uma seção do PPC.
        pagina (int): Página em que a explicação se encontra.
        esperado (str): Passagem que deve estar no trecho recuperado.
    """
    trecho = base_real.buscar(pergunta)[0]
    assert trecho.pagina == pagina
    assert esperado in trecho.texto
    assert '.....' not in trecho.texto


def test_esquema_gemini_solicita_referencias():
    """Peça somente números; o servidor recupera as passagens originais."""
    mensagens = [{'content': 'Instruções.'}, {'content': 'Contexto.'}]
    esquema = payload_geracao(mensagens)['generationConfig']['responseSchema']
    assert esquema['required'] == ['status', 'trechos']
    assert esquema['properties']['trechos']['items']['type'] == 'INTEGER'
    assert 'afirmacoes' not in esquema['properties']


def test_referencias_preservam_formatacao_e_ressalvas():
    """Elimine a necessidade de o gerador copiar espaços e quebras de linha."""
    texto = 'A biblioteca\nnão abre no feriado.\n\nO horário regular permanece o mesmo.'
    trecho = TrechoDocumento('aviso.txt', None, texto)
    bruto = json.dumps({'status': 'respondida', 'trechos': [1]})
    resposta = interpretar(bruto, [trecho], 1.0)
    assert resposta.encontrou
    assert resposta.texto == texto + ' [aviso.txt]'
    assert resposta.fontes == (trecho,)


@pytest.mark.parametrize('referencias', [[True], [False], [1.0], [-1], [0], [9], [], [1] * 6, '1'])
def test_referencias_invalidas_nao_criam_fontes(referencias):
    """Recuse números ausentes do contexto, tipos incorretos e listas excessivas.

    Args:
        referencias: Seleção inválida recebida do gerador.
    """
    bruto = json.dumps({'status': 'respondida', 'trechos': referencias})
    resposta = interpretar(bruto, [TrechoDocumento('fonte.txt', None, 'Texto público.')], 1)
    assert not resposta.encontrou and not resposta.fontes


def test_texto_inventado_e_ignorado_quando_ha_referencias():
    """Exiba apenas o texto original, mesmo se houver campos textuais extras."""
    fonte = TrechoDocumento('horarios.txt', None, 'A biblioteca abre às 8h.')
    bruto = json.dumps({'status': 'respondida', 'trechos': [1],
                        'afirmacoes': [{'texto': 'A biblioteca foi fechada.', 'fontes': [1]}]})
    resposta = interpretar(bruto, [fonte], 1.0)
    assert resposta.encontrou and 'abre às 8h' in resposta.texto
    assert 'fechada' not in resposta.texto


class GeradorReferencias:
    """Seleção controlada para testar o encadeamento, sem implementar outro modelo."""

    def gerar(self, mensagens):
        """Selecione a primeira evidência do contexto montado pelo consultor.

        Args:
            mensagens (list): Instruções e fontes fornecidas no teste.

        Returns:
            str: Seleção de um identificador, como no contrato REST.
        """
        return json.dumps({'status': 'respondida', 'trechos': [1]})


def test_chatbot_responde_parafrase_com_fonte(base_real):
    """Exercite recuperação, seleção e conversão da resposta em conjunto.

    Args:
        base_real: Busca sobre o acervo incluído.
    """
    consultor = ConsultorRAG(base_real, GeradorReferencias(), limiar_similaridade=base_real.limiar_relevancia)
    bot = Chatbot(consultor)
    resposta = asyncio.run(bot.processar_mensagem('parafrase', 'Preciso saber se a faculdade cobra mensalidade.'))
    assert resposta.sucesso and 'gratuitos' in resposta.texto
    assert resposta.fontes[0].arquivo == 'FAQ_secretaria.txt'


@pytest.fixture
def base_isolada(tmp_path):
    """Disponibilize uma base vazia para publicações isoladas de teste.

    Args:
        tmp_path: Diretório temporário criado pelo pytest.

    Yields:
        BaseTextual: Busca sem os documentos iniciais.
    """
    engine = abrir_sqlite(str(tmp_path / 'acervo.db'))
    try:
        yield BaseTextual(RepositorioTrechos(engine))
    finally:
        engine.dispose()


def test_calendario_publicado_responde_a_pergunta_da_imagem(tmp_path, base_isolada):
    """Recupere um calendário isolado de teste quando a data realmente estiver no acervo.

    Args:
        tmp_path: Diretório temporário do teste, fora dos documentos entregues.
        base_isolada: Acervo temporário sem as fontes iniciais.
    """
    arquivo = tmp_path / 'calendario_teste.txt'
    arquivo.write_text('Provas de Banco de Dados: dia 20/11/2026, às 19h, na sala 5.', encoding='utf-8')
    base_isolada.indexar_arquivo(arquivo)
    consultor = ConsultorRAG(base_isolada, GeradorReferencias(), limiar_similaridade=base_isolada.limiar_relevancia)
    resposta = asyncio.run(Chatbot(consultor).processar_mensagem('calendario', 'Quando é a prova de Banco de Dados?'))
    assert resposta.sucesso and '20/11/2026' in resposta.texto


def test_503_e_repetido_com_limite(monkeypatch):
    """Recupere uma indisponibilidade transitória sem repetir indefinidamente.

    Args:
        monkeypatch: Substituição da espera real durante o teste.
    """
    respostas = iter([httpx.Response(503), httpx.Response(500), httpx.Response(200, json={'ok': True})])
    esperas = []
    monkeypatch.setattr('infra.gemini_http.time.sleep', esperas.append)
    api = ClienteGemini('chave-apenas-teste', httpx.MockTransport(lambda _: next(respostas)))
    try:
        assert api.chamar('modelo-teste', 'generateContent', {}) == {'ok': True}
    finally:
        api.fechar()
    assert esperas == [1, 2]


def test_geracao_nao_repete_cota_diaria(monkeypatch):
    """Não aplique a repetição de 503 a respostas de cota esgotada.

    Args:
        monkeypatch: Substituição do relógio de espera.
    """
    chamadas, esperas = [], []
    monkeypatch.setattr('infra.gemini_http.time.sleep', esperas.append)
    transporte = httpx.MockTransport(lambda r: chamadas.append(r) or httpx.Response(429, json={'error': {}}))
    api = ClienteGemini('chave-apenas-teste', transporte)
    try:
        with pytest.raises(ErroGemini):
            api.chamar('modelo-teste', 'generateContent', {})
    finally:
        api.fechar()
    assert len(chamadas) == 1 and not esperas


def test_geracao_nao_repete_fora_do_prazo(monkeypatch):
    """Não consuma o prazo restante esperando uma nova tentativa.

    Args:
        monkeypatch: Substituição do orçamento temporal da operação.
    """
    monkeypatch.setattr('infra.gemini_http.restante', lambda: 0.5)
    assert not repetir_geracao(httpx.Response(503), 0)
    assert not repetir_geracao(httpx.Response(503), 2)
    assert not repetir_geracao(httpx.Response(400), 0)
