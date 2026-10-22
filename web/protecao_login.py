"""Composição e tradução HTTP do módulo independente de autenticação."""
import logging
from starlette.responses import JSONResponse
from seguranca.armazenamento import RepositorioLoginSQLite
from seguranca.autenticacao import AutenticadorSecretaria
from seguranca.contratos import CredenciaisInvalidas, LoginIndisponivel, FalhaSeguranca, TentativasExcedidas
from web.senhas import conferir

logger = logging.getLogger(__name__)


def configurar_login(estado):
    """Monte persistência separada e exija segundo fator no modo oficial."""
    repo = RepositorioLoginSQLite(estado.config.seguranca_db)
    estado.protecao_login = AutenticadorSecretaria(repo, estado.config, repo.segredo(), conferir,
                                                  exigir_2fa=estado.modo == 'oficial')


def registrar_erros(app):
    """Traduza exceções de segurança sem acoplar o domínio a FastAPI."""
    app.add_exception_handler(CredenciaisInvalidas, erro_credenciais)
    app.add_exception_handler(TentativasExcedidas, erro_tentativas)
    app.add_exception_handler(LoginIndisponivel, erro_protecao)
    app.add_exception_handler(FalhaSeguranca, erro_protecao)


async def erro_credenciais(request, erro):
    """Retorne o mesmo diagnóstico para conta, senha ou TOTP inválido."""
    return JSONResponse({'detail': 'Credenciais inválidas.'}, 401)


async def erro_tentativas(request, erro):
    """Informe espera sem revelar qual cota, conta ou IP atingiu o limite."""
    return JSONResponse({'detail': 'Muitas tentativas. Aguarde para tentar novamente.'},
                        429, headers={'Retry-After': str(erro.segundos)})


async def erro_protecao(request, erro):
    """Falhe fechada quando faltar configuração ou a proteção estiver indisponível."""
    logger.warning('Falha de autenticação: %s', type(erro).__name__)
    return JSONResponse({'detail': 'Autenticação indisponível. Contate o responsável.'}, 503)
