import hashlib
import hmac
from fastapi import HTTPException, Request


def limitar(request, categoria, limite):
    """Aplique limite por representação HMAC do IP; lance HTTPException 429 ao exceder."""
    estado = request.app.state
    ip = request.client.host if request.client else 'local'
    chave = hmac.new(estado.sal_ip, ip.encode(), hashlib.sha256).hexdigest()
    if not limite.permitir(categoria + ':' + chave):
        raise HTTPException(429, 'Limite de requisições. Aguarde um minuto.')


def sessao_atual(request: Request):
    """Retorne a sessão do cookie ou lance HTTPException 401 se estiver ausente ou expirada."""
    sessao = request.app.state.sessoes.obter(request.cookies.get('consultor'))
    if sessao is None:
        raise HTTPException(401, 'Sessão expirou. Reabra o atendimento.')
    return sessao


def proteger_escrita(request: Request):
    """Exija origem compatível e token CSRF da sessão para operações de escrita."""
    sessao = sessao_atual(request)
    origem = request.headers.get('origin')
    if origem is not None and origem != request.app.state.config.origem:
        raise HTTPException(403, 'Origem não permitida.')
    if not hmac.compare_digest(request.headers.get('x-csrf-token', '').encode(), sessao.csrf.encode()):
        raise HTTPException(403, 'Token de sessão inválido.')
    return sessao


def exigir_admin(request: Request):
    """Exija sessão administrativa não expirada em toda operação protegida."""
    sessao = sessao_atual(request)
    if not sessao.admin or sessao.admin_fim <= request.app.state.sessoes.relogio():
        raise HTTPException(401, 'Entre como administrador.')
    return sessao


def admin_escrita(request: Request):
    """Exija simultaneamente proteção CSRF e autorização administrativa."""
    proteger_escrita(request)
    return exigir_admin(request)


def cookie(response, token, config):
    """Defina cookie técnico HttpOnly, SameSite e Secure conforme a origem configurada."""
    response.set_cookie('consultor', token, httponly=True, secure=config.seguro,
                        samesite='strict', max_age=config.ttl, path='/')
