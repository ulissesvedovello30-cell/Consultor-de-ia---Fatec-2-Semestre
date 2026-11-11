"""Embeddings remotos e seleção de evidências por Gemini; nenhum modelo local."""
import json
import time
import numpy as np
from infra.gemini_http import ErroGemini, nome_modelo
from servicos.prazo import restante

ESQUEMA = {'type': 'OBJECT', 'required': ['status', 'trechos'], 'properties': {
    'status': {'type': 'STRING', 'enum': ['respondida', 'insuficiente']},
    'trechos': {'type': 'ARRAY', 'items': {'type': 'INTEGER'}, 'maxItems': 5}}}


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


DIMENSAO_INDICE = 768


def ler_valores(objeto):
    """Extraia os números de um embedding sem incluir o conteúdo nos erros.

    Args:
        objeto (dict): Resposta com embedding.values.

    Returns:
        ndarray: Vetor unidimensional com números finitos.
    """
    try:
        vetor = np.asarray(objeto['embedding']['values'])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ErroGemini('Resposta sem embedding.values numérico válido.') from None
    if vetor.ndim != 1 or vetor.dtype.kind not in 'ifu':
        raise ErroGemini('Embedding sem uma lista unidimensional de números.')
    if not np.isfinite(vetor).all():
        raise ErroGemini('Embedding contém valor não finito.')
    return vetor.astype(np.float64)


def selecionar_dimensao(vetor, modelo):
    """Selecione o prefixo MRL apenas para o modelo e tamanho conhecidos.

    Args:
        vetor (ndarray): Valores já validados.
        modelo (str): Modelo que gerou o vetor.

    Returns:
        ndarray: Coordenadas que correspondem ao índice de 768 dimensões.
    """
    if vetor.size == DIMENSAO_INDICE:
        return vetor
    if modelo == 'gemini-embedding-001' and vetor.size == 3072:
        return vetor[:DIMENSAO_INDICE]
    raise ErroGemini(f'Embedding com {vetor.size} dimensões; o índice exige {DIMENSAO_INDICE}.')


def vetor_validado(objeto, modelo=None):
    """Prepare o mesmo vetor unitário para indexação e consulta.

    Args:
        objeto (dict): Resposta do provedor.
        modelo (str | None): Identificador usado na chamada.

    Returns:
        ndarray: Vetor normalizado, em float32, pronto para o acervo.
    """
    vetor = selecionar_dimensao(ler_valores(objeto), modelo)
    escala = np.max(np.abs(vetor))
    if escala == 0:
        raise ErroGemini('Embedding de norma zero nas 768 dimensões do índice.')
    vetor = vetor / escala
    return (vetor / np.linalg.norm(vetor)).astype(np.float32)


class EmbeddingsGemini:
    """Crie vetores remotos com tipos distintos para documentos e perguntas."""

    def __init__(self, cliente, modelo):
        """Receba cliente e modelo; inclua dimensão e tarefa na identidade do índice."""
        self.cliente, self.modelo = cliente, nome_modelo(modelo)
        self.nome_modelo = f'{self.modelo}:768:retrieval:v1'

    def codificar(self, textos):
        """Retorne matriz normalizada dos textos documentais na mesma ordem."""
        from infra.retomada_lotes import obter_lote
        lotes = [obter_lote(self._lote, self.nome_modelo, textos[i:i + 32]) for i in range(0, len(textos), 32)]
        return np.vstack(lotes) if lotes else np.empty((0, 768), dtype=np.float32)

    def _lote(self, textos):
        """Envie até 32 trechos juntos e valide a quantidade de vetores retornados.

        Args:
            textos (list[str]): Trechos públicos na ordem de indexação.

        Returns:
            ndarray: Matriz normalizada na mesma ordem.

        Raises:
            ErroGemini: Se a resposta estiver incompleta ou os vetores forem inválidos.
        """
        pedidos = [payload_embedding(self.modelo, t, 'RETRIEVAL_DOCUMENT') for t in textos]
        objeto = self.cliente.chamar(self.modelo, 'batchEmbedContents', {'requests': pedidos})
        try:
            vetores = objeto['embeddings']
            (True,).index(isinstance(vetores, list) and len(vetores) == len(textos))
        except (KeyError, TypeError, ValueError):
            raise ErroGemini('Lote de embeddings incompleto ou inválido.') from None
        return np.array([vetor_validado({'embedding': v}, self.modelo) for v in vetores], dtype=np.float32)

    def consulta(self, texto):
        """Retorne o vetor da pergunta com tarefa RETRIEVAL_QUERY."""
        return self._vetor(texto, 'RETRIEVAL_QUERY')

    def _vetor(self, texto, tarefa):
        """Envie texto com truncamento desativado e retorne vetor validado."""
        dados = payload_embedding(self.modelo, texto, tarefa)
        return vetor_validado(self.cliente.chamar(self.modelo, 'embedContent', dados), self.modelo)


def juntar_partes(partes):
    """Retorne só o texto final, excluindo blocos marcados como pensamento."""
    return ''.join(p['text'] for p in partes if not p.get('thought', False))


def payload_embedding(modelo, texto, tarefa):
    """Monte a requisição REST de embedding sem truncamento silencioso.

    Args:
        modelo (str): Nome validado do modelo Gemini.
        texto (str): Texto público revisado.
        tarefa (str): RETRIEVAL_DOCUMENT ou RETRIEVAL_QUERY.

    Returns:
        dict: Requisição compatível com chamadas individuais e em lote.
    """
    return {'model': 'models/' + modelo, 'content': {'parts': [{'text': texto}]},
            'embedContentConfig': {'taskType': tarefa, 'outputDimensionality': 768, 'autoTruncate': False}}
