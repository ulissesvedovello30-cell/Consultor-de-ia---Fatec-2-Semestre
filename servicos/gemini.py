"""Embeddings remotos e seleção de evidências por Gemini; nenhum modelo local."""
import json
import time
import numpy as np
from infra.gemini_http import ErroGemini, nome_modelo
from servicos.prazo import restante

AFIRMACAO = {'type': 'OBJECT', 'required': ['texto', 'fontes'], 'properties': {
    'texto': {'type': 'STRING'}, 'fontes': {'type': 'ARRAY', 'items': {'type': 'INTEGER'}}}}
ESQUEMA = {'type': 'OBJECT', 'required': ['status', 'afirmacoes'], 'properties': {
    'status': {'type': 'STRING', 'enum': ['respondida', 'insuficiente']},
    'afirmacoes': {'type': 'ARRAY', 'items': AFIRMACAO}}}


def payload_geracao(mensagens):
    """Converta instruções confiáveis e contexto não confiável em corpo REST."""
    return {'systemInstruction': {'parts': [{'text': mensagens[0]['content']}]},
        'contents': [{'role': 'user', 'parts': [{'text': mensagens[1]['content']}]}],
        'generationConfig': {'temperature': 0, 'maxOutputTokens': 4096,
            'responseMimeType': 'application/json', 'responseSchema': ESQUEMA}}


def texto_candidato(objeto):
    """Extraia texto apenas de candidato concluído, recusando bloqueios e truncamentos."""
    try:
        candidato = objeto['candidates'][0]
        if candidato['finishReason'] != 'STOP':
            raise ValueError('Geração não concluída.')
        texto = juntar_partes(candidato['content']['parts'])
        if not texto.strip() or len(texto) > 16000:
            raise ValueError('Tamanho inválido.')
        return texto
    except (KeyError, IndexError, TypeError, ValueError):
        raise ErroGemini('Gemini não devolveu uma resposta completa utilizável.') from None


class GeradorGemini:
    """Selecione evidências do acervo sem habilitar pesquisa, execução ou ferramentas."""

    def __init__(self, cliente, modelo):
        """Receba cliente autenticado e identificador disponível na conta Google."""
        self.cliente, self.modelo = cliente, nome_modelo(modelo)

    def gerar_com_prazo(self, mensagens, prazo_final):
        """Retorne JSON do modelo dentro do orçamento definido pelo executor RAG."""
        if time.monotonic() >= prazo_final:
            raise TimeoutError('Prazo excedido antes da geração.')
        objeto = self.cliente.chamar(self.modelo, 'generateContent', payload_geracao(mensagens))
        return texto_candidato(objeto)


def vetor_validado(objeto):
    """Retorne vetor normalizado de 768 posições; rejeite forma, NaN e norma zero."""
    try:
        vetor = np.asarray(objeto['embedding']['values'], dtype=np.float32)
        norma = np.linalg.norm(vetor)
        if vetor.shape != (768,) or not np.isfinite(vetor).all() or not norma > 0:
            raise ValueError('Vetor inválido.')
        return vetor / norma
    except (KeyError, TypeError, ValueError):
        raise ErroGemini('Embedding incompatível ou inválido.') from None


class EmbeddingsGemini:
    """Crie vetores remotos com tipos distintos para documentos e perguntas."""

    def __init__(self, cliente, modelo):
        """Receba cliente e modelo; inclua dimensão e tarefa na identidade do índice."""
        self.cliente, self.modelo = cliente, nome_modelo(modelo)
        self.nome_modelo = f'{modelo}:768:retrieval:v1'

    def codificar(self, textos):
        """Retorne matriz normalizada dos textos documentais na mesma ordem."""
        return np.array([self._vetor(t, 'RETRIEVAL_DOCUMENT') for t in textos], dtype=np.float32)

    def consulta(self, texto):
        """Retorne o vetor da pergunta com tarefa RETRIEVAL_QUERY."""
        return self._vetor(texto, 'RETRIEVAL_QUERY')

    def _vetor(self, texto, tarefa):
        """Envie texto com truncamento desativado e retorne vetor validado."""
        dados = {'content': {'parts': [{'text': texto}]}, 'embedContentConfig': {
            'taskType': tarefa, 'outputDimensionality': 768, 'autoTruncate': False}}
        return vetor_validado(self.cliente.chamar(self.modelo, 'embedContent', dados))


def juntar_partes(partes):
    """Retorne só o texto final, excluindo blocos marcados como pensamento."""
    return ''.join(p['text'] for p in partes if not p.get('thought', False))
