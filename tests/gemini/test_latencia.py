"""Parâmetros documentados e orçamento real de transporte do gerador."""
import time
import httpx
from aplicacao.servicos.gemini.gemini import payload_geracao, GeradorGemini
from aplicacao.infra.gemini.gemini_http import ClienteGemini, timeout_http
from aplicacao.servicos.respostas.prazo import FIM


def test_gemini_3_usa_raciocinio_baixo_sem_forcar_temperatura():
    mensagens = [{'content': 'Sistema.'}, {'content': 'Contexto.'}]
    cfg = payload_geracao(mensagens, 'gemini-3.5-flash')['generationConfig']
    assert cfg['thinkingConfig'] == {'thinkingLevel': 'LOW'}
    assert 'temperature' not in cfg
    assert cfg['responseMimeType'] == 'application/json'


def test_modelo_anterior_nao_recebe_parametro_exclusivo_do_gemini_3():
    cfg = payload_geracao([{'content': 'S'}, {'content': 'C'}], 'gemini-2.0-flash')['generationConfig']
    assert 'thinkingConfig' not in cfg and cfg['temperature'] == 0


def test_leitura_usa_orcamento_restante_sem_aumentar_prazo_total():
    token = FIM.set(time.monotonic() + 55)
    try:
        timeout = timeout_http('/models/gemini-3.5-flash:generateContent')
        assert 50 < timeout.read <= 55
        assert timeout.connect <= 5 and timeout.pool <= 2
    finally:
        FIM.reset(token)


def test_chamada_direta_do_gerador_respeita_o_prazo_recebido():
    vistos = []
    def receber(req):
        vistos.append(req.extensions['timeout'])
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': '{"status":"insuficiente","trechos":[]}'}]}}]})
    api = ClienteGemini('chave-de-teste', httpx.MockTransport(receber))
    try:
        GeradorGemini(api, 'gemini-3.5-flash').gerar_com_prazo([{'content': 'S'}, {'content': 'C'}], time.monotonic() + 2)
    finally:
        api.fechar()
    assert 0 < vistos[0]['read'] <= 2 and FIM.get() is None
