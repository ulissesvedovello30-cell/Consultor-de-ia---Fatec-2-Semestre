import asyncio
import logging
import secrets
import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from core.limitador import LimitadorTaxa
from dominio.erros import ErroBancoDeDados, ErroIndexacao
from infra.gemini_http import ErroGemini
from web.configuracao import ConfigWeb
from web.sessoes import Sessoes
from web.middleware import cabecalhos
from seguranca.gateway import GatewaySeguranca
from seguranca.trafego import ControleTrafego
from web.protecao_login import configurar_login, registrar_erros
from web import rotas_chat, rotas_documentos, rotas_sessao

STATIC = Path(__file__).parent / 'static'
logger = logging.getLogger(__name__)


def criar_app(fabrica=None, configuracao=None, modo='oficial'):
    """Monte aplicação, rotas, ciclo de vida, segurança e tratamento de exceções.
    
    Args:
        fabrica: Gerenciador de recursos injetável, oficial ou demonstrativo.
        configuracao: Configuração web opcional usada por execução ou testes.
        modo: Rótulo explícito do ambiente: oficial ou debug.
    
    Returns:
        Aplicação FastAPI pronta para inicialização.
    """
    from montagem import abrir_chatbot
    config = configuracao or ConfigWeb.ambiente()
    app = FastAPI(lifespan=ciclo(fabrica or abrir_chatbot), docs_url=None, redoc_url=None, openapi_url=None)
    configurar_estado(app.state, config, modo)
    configurar_rotas(app)
    instalar_gateway(app)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(config.origem).hostname])
    app.middleware('http')(cabecalhos)
    configurar_erros(app)
    return app


def ciclo(fabrica):
    """Retorne gerenciador assíncrono de inicialização e encerramento dos recursos."""
    @asynccontextmanager
    async def lifespan(app):
        """Disponibilize dependências compartilhadas e garanta fechamento ao encerrar."""
        contexto = fabrica()
        app.state.chatbot, app.state.base = await asyncio.to_thread(contexto.__enter__)
        limpeza = asyncio.create_task(expirar_estado(app.state))
        try:
            yield
        finally:
            await encerrar(limpeza, contexto)
    return lifespan


def configurar_estado(estado, config, modo):
    """Configure limites, sessões e controle de concorrência compartilhados pela aplicação."""
    estado.config, estado.modo = config, modo
    estado.sessoes = Sessoes(config.ttl)
    estado.sal_ip = secrets.token_bytes(32)
    estado.upload_vaga = threading.BoundedSemaphore(1)
    estado.limite_sessao = LimitadorTaxa(30, 60)
    configurar_login(estado)
    estado.trafego = ControleTrafego()
    estado.limite_chat = LimitadorTaxa(30, 60)
    estado.limite_global = LimitadorTaxa(60, 60)
    estado.limite_upload = LimitadorTaxa(20, 60)


def configurar_rotas(app):
    """Registre API e arquivos estáticos do frontend na mesma origem."""
    for rotas in (rotas_chat, rotas_sessao, rotas_documentos):
        app.include_router(rotas.router)
    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    app.add_api_route('/', pagina, methods=['GET'])


async def pagina():
    """Retorne a página inicial estática, sem interpolação de conteúdo externo."""
    return FileResponse(STATIC / 'index.html')


def configurar_erros(app):
    """Registre conversores de exceções para respostas HTTP sanitizadas."""
    app.add_exception_handler(ErroBancoDeDados, erro_banco)
    app.add_exception_handler(ErroIndexacao, erro_documento)
    app.add_exception_handler(ErroGemini, erro_provedor)
    app.add_exception_handler(TimeoutError, erro_prazo)
    app.add_exception_handler(RequestValidationError, erro_validacao)
    app.add_exception_handler(Exception, erro_inesperado)
    registrar_erros(app)


async def erro_banco(request: Request, erro):
    """Retorne HTTP 503 sem revelar consultas, credenciais ou parâmetros do banco."""
    logger.warning('Falha de infraestrutura: %s', type(erro).__name__)
    return JSONResponse({'detail': 'Acervo indisponível. Tente novamente.'}, 503)


async def erro_documento(request: Request, erro):
    """Retorne HTTP 422 com o diagnóstico público da validação documental."""
    return JSONResponse({'detail': str(erro)}, 422)


async def erro_validacao(request: Request, erro):
    """Retorne HTTP 422 sem reproduzir campos recebidos, inclusive senhas."""
    return JSONResponse({'detail': 'Dados inválidos. Confira campos, datas e limites.'}, 422)


async def erro_inesperado(request: Request, erro):
    """Registre somente a classe do erro e devolva mensagem HTTP 500 genérica."""
    logger.error('Erro interno: %s', type(erro).__name__)
    return JSONResponse({'detail': 'Não foi possível concluir a operação.'}, 500)


async def expirar_estado(estado):
    """Remova contexto, sessões e limites vencidos a cada 30 segundos."""
    while True:
        await asyncio.sleep(30)
        estado.chatbot.expirar()
        estado.sessoes.obter(None)
        expirar_limites(estado)
        await limpar_seguranca(estado)


async def erro_provedor(request: Request, erro):
    """Converta falha remota em indisponibilidade sem expor o corpo do provedor."""
    logger.warning('Falha externa: %s', type(erro).__name__)
    return JSONResponse({'detail': 'Gemini indisponível. Confira chave, modelo e cota no servidor.'}, 503)


async def erro_prazo(request: Request, erro):
    """Informe prazo excedido preservando a versão publicada anteriormente."""
    return JSONResponse({'detail': 'Prazo excedido; confira o acervo antes de repetir.'}, 504)


async def encerrar(limpeza, contexto):
    """Cancele a limpeza periódica e feche os recursos compartilhados."""
    limpeza.cancel()
    with suppress(asyncio.CancelledError):
        await limpeza
    await asyncio.to_thread(contexto.__exit__, None, None, None)


def expirar_limites(estado):
    """Expire identificadores temporários de IP e limites de conversa."""
    for nome in ('sessao', 'chat', 'global', 'upload'):
        getattr(estado, 'limite_' + nome).expirar()
    estado.chatbot._limitador.expirar()


def instalar_gateway(app):
    """Instale validação HTTP usando os serviços já compostos na aplicação."""
    app.add_middleware(GatewaySeguranca, trafego=app.state.trafego, sal=app.state.sal_ip)


async def limpar_seguranca(estado):
    """Expire proteção temporária sem derrubar a limpeza se o SQLite estiver ocupado."""
    import time
    from seguranca.contratos import FalhaSeguranca
    estado.trafego.expirar()
    try:
        await asyncio.to_thread(estado.protecao_login.repo.limpar, time.time())
    except FalhaSeguranca:
        logger.warning('Limpeza da proteção temporariamente indisponível.')
