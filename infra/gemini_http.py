"""Cliente REST restrito ao Gemini, sem ferramentas, redirecionamentos ou logs de conteúdo."""
import re
import httpx
from servicos.prazo import restante

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta'


class ErroGemini(RuntimeError):
    """Falha sanitizada do provedor; não contém chave, prompt ou corpo remoto."""


def nome_modelo(nome):
    """Valide e retorne um identificador simples de modelo configurado."""
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}', nome):
        raise ValueError('Configure um identificador de modelo válido no .env.')
    return nome


def corpo_json(resposta):
    """Valide HTTP e JSON; retorne um objeto ou lance ErroGemini sanitizado."""
    try:
        resposta.raise_for_status()
        objeto = resposta.json()
        if not isinstance(objeto, dict):
            raise ValueError('Objeto esperado.')
        return objeto
    except httpx.HTTPStatusError as erro:
        raise ErroGemini(f'Gemini indisponível (HTTP {erro.response.status_code}).') from None
    except ValueError:
        raise ErroGemini('Gemini devolveu uma resposta inválida.') from None


class ClienteGemini:
    """Realize chamadas autenticadas com timeout e transporte injetável em testes."""

    def __init__(self, chave, transporte=None):
        """Receba chave privada e transporte HTTP opcional; não faça chamadas aqui."""
        if not chave.strip():
            raise ValueError('Preencha GEMINI_API_KEY no .env ou execute --demo.')
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
            resposta = self._http.request(metodo, caminho, json=dados, timeout=restante())
            return corpo_json(resposta)
        except httpx.TimeoutException:
            raise TimeoutError('Gemini excedeu o prazo de comunicação.') from None
        except httpx.RequestError:
            raise ErroGemini('Não foi possível comunicar com o Gemini.') from None

    def fechar(self):
        """Libere conexões HTTP persistentes."""
        self._http.close()
