"""Cliente REST restrito ao Gemini, sem ferramentas, redirecionamentos ou logs de conteúdo."""
import re
import logging
import time
import httpx
from aplicacao.servicos.respostas.prazo import restante
from aplicacao.infra.gemini.cota_gemini import descrever_cota, tentar_novamente

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta'
logger = logging.getLogger(__name__)


class ErroGemini(RuntimeError):
    """Falha sanitizada do provedor; não contém chave, prompt ou corpo remoto."""


class ErroCotaGemini(ErroGemini):
    """Cota do Gemini atingida, com diagnóstico sanitizado pelo cliente HTTP."""


def chave_gemini(valor):
    """Obtenha a credencial privada sem modificar o .env nem expor seu valor.

    Args:
        valor (str): Valor de GEMINI_API_KEY, com ou sem o rótulo de cópia.

    Returns:
        str: Chave que será usada no cabeçalho HTTP.

    Raises:
        ValueError: Se a chave estiver vazia ou contiver espaço ou controle.
    """
    chave = re.sub(r'^API do gemini:[ \t]*', '', valor.strip(), flags=re.I)
    if not chave:
        raise ValueError('Este chatbot exige Gemini. Preencha GEMINI_API_KEY no .env ao lado de main.py.')
    if not (chave.isascii() and chave.isprintable()) or any(c.isspace() for c in chave):
        raise ValueError('GEMINI_API_KEY deve conter apenas a chave, sem espaços ou rótulos.')
    return chave


def nome_modelo(nome, campo='Modelo Gemini'):
    """Valide o nome curto ou o recurso models/<id>.

    Args:
        nome (str): Identificador configurado.
        campo (str): Nome da configuração para o diagnóstico.

    Returns:
        str: Identificador sem o prefixo REST.

    Raises:
        ValueError: Se o identificador contiver segmentos ou caracteres inválidos.
    """
    nome = nome.strip().removeprefix('models/')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}', nome):
        raise ValueError(f'{campo} inválido no .env. Use o ID do modelo, sem URL. Consulte ferramentas.diagnostico.verificar_gemini.')
    return nome


def motivo_recusa(resposta):
    """Identifique causas conhecidas do HTTP 400 sem reproduzir a resposta.

    Args:
        resposta (httpx.Response): Resposta recebida do provedor.

    Returns:
        str: Orientação local que não inclui dados da requisição.
    """
    try:
        erro = resposta.json()['error']
        detalhes = erro.get('details', [])
        motivos = {item.get('reason') for item in detalhes if isinstance(item, dict)}
        status = erro.get('status')
    except (ValueError, KeyError, TypeError, AttributeError):
        return 'O provedor rejeitou a requisição.'
    return orientar_recusa(motivos, status)


def orientar_recusa(motivos, status):
    """Retorne uma orientação segura para os motivos de rejeição identificados.

    Args:
        motivos (set): Códigos de erro recebidos do provedor.
        status (str): Categoria da falha na resposta remota.

    Returns:
        str: Orientação sem conteúdo privado da requisição.
    """
    if 'API_KEY_INVALID' in motivos:
        return 'O Google recusou GEMINI_API_KEY. Confira a credencial da conta.'
    if status == 'FAILED_PRECONDITION':
        return 'Confira os requisitos de acesso do projeto no Google AI Studio.'
    return 'Confira o modelo, os campos da requisição e o acesso da chave.'


def corpo_json(resposta):
    """Valide HTTP e JSON; retorne um objeto ou lance ErroGemini sanitizado."""
    try:
        resposta.raise_for_status()
        objeto = resposta.json()
        if not isinstance(objeto, dict):
            raise ValueError('Objeto esperado.')
        return objeto
    except httpx.HTTPStatusError as erro:
        raise erro_http(erro.response) from None
    except ValueError:
        raise ErroGemini('Gemini devolveu uma resposta inválida.') from None


def erro_http(resposta):
    """Converta falhas HTTP do provedor em exceções sanitizadas.

    Args:
        resposta (httpx.Response): Resposta de erro recebida pelo transporte.

    Returns:
        ErroGemini: Exceção que não contém a chave nem o corpo remoto.
    """
    codigo = resposta.status_code
    diagnosticos = {429: descrever_cota, 400: motivo_recusa}
    try:
        classe = ErroCotaGemini if codigo == 429 else ErroGemini
        return classe(f'Gemini (HTTP {codigo}): ' + diagnosticos[codigo](resposta))
    except KeyError:
        return ErroGemini(f'Gemini indisponível (HTTP {codigo}).')


class ClienteGemini:
    """Realize chamadas autenticadas com timeout e transporte injetável em testes."""

    def __init__(self, chave, transporte=None):
        """Receba chave privada e transporte HTTP opcional; não faça chamadas aqui."""
        chave = chave_gemini(chave)
        self._http = httpx.Client(base_url=ENDPOINT, transport=transporte,
            headers={'x-goog-api-key': chave}, follow_redirects=False, trust_env=False)

    def chamar(self, modelo, metodo, dados):
        """Envie dados ao método de modelo e retorne JSON, com falhas sanitizadas."""
        caminho = f'/models/{nome_modelo(modelo)}:{metodo}'
        return self._enviar('POST', caminho, dados)

    def modelos(self):
        """Retorne a primeira página de modelos disponíveis à chave configurada."""
        return self._enviar('GET', '/models?pageSize=1000', None)

    def _enviar(self, metodo, caminho, dados):
        """Execute HTTP com timeout por fase limitado pelo orçamento da operação."""
        try:
            for tentativa in range(7):
                resposta = self._http.request(metodo, caminho, json=dados, timeout=timeout_http(caminho))
                if not repetir_resposta(resposta, caminho, tentativa):
                    return corpo_json(resposta)
        except httpx.TimeoutException:
            raise TimeoutError('Gemini excedeu o prazo de comunicação.') from None
        except httpx.RequestError:
            raise ErroGemini('Não foi possível comunicar com o Gemini.') from None

    def fechar(self):
        """Libere conexões HTTP persistentes."""
        self._http.close()


def timeout_http(caminho):
    """Reserve conexões curtas e limite a leitura ao orçamento real da operação.

    Args:
        caminho (str): Método do endpoint restrito do Gemini.

    Returns:
        httpx.Timeout: Limites por fase, sem ultrapassar o prazo externo.
    """
    segundos = restante(limite=180.0) if caminho.endswith(':generateContent') else restante()
    return httpx.Timeout(segundos, connect=min(5.0, segundos), write=min(10.0, segundos), pool=min(2.0, segundos))


def repetir_resposta(resposta, caminho, tentativa):
    """Aplique políticas distintas para cota de embeddings e falha temporária de geração.

    Args:
        resposta (httpx.Response): Resposta recebida do provedor.
        caminho (str): Método chamado no endpoint restrito.
        tentativa (int): Número da tentativa atual, iniciado em zero.

    Returns:
        bool: True quando uma nova chamada está autorizada pelo prazo e pela política.
    """
    if caminho.endswith(':batchEmbedContents'):
        return tentar_novamente(resposta, tentativa)
    if caminho.endswith(':generateContent'):
        return repetir_geracao(resposta, tentativa)
    return False


def repetir_geracao(resposta, tentativa):
    """Repita até duas falhas 500/503 sem insistir em erros de cota ou de configuração.

    Args:
        resposta (httpx.Response): Resultado da geração.
        tentativa (int): Tentativa atual dentro da operação.

    Returns:
        bool: True após a espera curta, respeitando o orçamento temporal.
    """
    if resposta.status_code not in (500, 503) or tentativa >= 2:
        return False
    espera = 2 ** tentativa
    if restante() <= espera:
        return False
    logger.warning('gemini_transitorio http=%d repeticao=%d espera=%ds', resposta.status_code, tentativa + 1, espera)
    time.sleep(espera)
    return True
