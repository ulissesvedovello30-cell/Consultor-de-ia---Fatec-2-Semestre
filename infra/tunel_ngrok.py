"""Túnel opcional; só importa e inicia ngrok mediante solicitação explícita."""
import os
from contextlib import contextmanager, nullcontext
from dataclasses import replace


def escolher_tunel(ativar, config):
    """Selecione execução local ou túnel sem abrir conexão no modo padrão.

    Args:
        ativar (bool): Opção --ngrok recebida pela CLI.
        config: Configuração web do servidor.

    Returns:
        ContextManager: Configuração local ou com a origem HTTPS do túnel.
    """
    fabricas = {False: local, True: abrir_tunel}
    return fabricas[ativar](config)


def local(config):
    """Mantenha a configuração original sem importar pyngrok.

    Args:
        config: Configuração web do servidor.

    Returns:
        ContextManager: Contexto sem recursos externos.
    """
    return nullcontext(config)


def parametros(config):
    """Exija token e proteção administrativa antes de publicar um túnel.

    Args:
        config: Configuração com senha e segundo fator.

    Returns:
        tuple: Token e porta local validados.

    Raises:
        ValueError: Se o ambiente estiver incompleto ou a porta for inválida.
    """
    token = os.getenv('NGROK_AUTHTOKEN', '').strip()
    try:
        (True,).index(bool(token and config.senha_hash and config.totp_segredo))
        porta = int(os.getenv('APP_PORT', '8000'))
        (True,).index(1 <= porta <= 65535)
    except ValueError:
        raise ValueError('Ngrok exige token, senha, TOTP e APP_PORT válida.') from None
    return token, porta


def conectar(token, porta):
    """Abra somente o túnel do servidor HTTP, somente para a aplicação web.

    Args:
        token (str): Credencial privada lida do ambiente.
        porta (int): Porta do servidor em loopback.

    Returns:
        tuple: API, configuração do agente e túnel HTTPS.

    Raises:
        RuntimeError: Se a dependência estiver ausente ou o túnel falhar.
    """
    ngrok, conf, erro_ngrok = carregar_ngrok()
    configuracao = conf.PyngrokConfig(auth_token=token, monitor_thread=False)
    try:
        tunel = ngrok.connect(addr=f'127.0.0.1:{porta}', proto='http', bind_tls=True, inspect=False, pyngrok_config=configuracao)
    except (erro_ngrok, OSError):
        ngrok.kill(pyngrok_config=configuracao)
        raise RuntimeError('Não foi possível abrir o túnel ngrok.') from None
    return ngrok, configuracao, tunel


def fechar(api, configuracao, tunel):
    """Encerre o agente ao sair, inclusive após falhas do aplicativo.

    Args:
        api: API pyngrok carregada somente quando necessária.
        configuracao: Configuração do agente iniciado.
        tunel: Túnel que pertence a esta execução.
    """
    try:
        api.disconnect(tunel.public_url, pyngrok_config=configuracao)
    finally:
        api.kill(pyngrok_config=configuracao)


@contextmanager
def abrir_tunel(config):
    """Mantenha o túnel apenas durante a execução do servidor.

    Args:
        config: Configuração web original.

    Yields:
        ConfigWeb: Configuração com host, origem e cookies HTTPS coerentes.
    """
    api, configuracao, tunel = conectar(*parametros(config))
    try:
        yield replace(config, origem=tunel.public_url.rstrip('/'))
    finally:
        fechar(api, configuracao, tunel)


def carregar_ngrok():
    """Carregue a dependência opcional apenas na abertura do túnel.

    Returns:
        tuple: API, configuração e classe de erro do pyngrok.

    Raises:
        RuntimeError: Se o pacote opcional não estiver instalado.
    """
    try:
        from pyngrok import ngrok, conf, exception
    except ImportError:
        raise RuntimeError('Instale requirements-ngrok.txt para usar o túnel.') from None
    return ngrok, conf, exception.PyngrokError
