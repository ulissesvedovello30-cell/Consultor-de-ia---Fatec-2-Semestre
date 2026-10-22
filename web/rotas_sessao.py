import asyncio
from fastapi import APIRouter, Request, Response, Depends, HTTPException
from pydantic import Field
from web.esquemas import ModeloEstrito
from web.seguranca import proteger_escrita, limitar, cookie

router = APIRouter()


class Credenciais(ModeloEstrito):
    usuario: str = Field(min_length=1, max_length=100)
    senha: str = Field(min_length=1, max_length=256)
    otp: str = Field(default='', max_length=6, pattern=r'^(?:[0-9]{6})?$')


@router.get('/api/sessao')
async def abrir_sessao(request: Request, response: Response):
    """Abra ou reutilize sessão anônima e retorne token CSRF, sem autenticar visitante."""
    estado = request.app.state
    limitar(request, 'sessao', estado.limite_sessao)
    token = request.cookies.get('consultor')
    sessao = estado.sessoes.obter(token)
    if sessao is None:
        token, sessao = estado.sessoes.criar()
        cookie(response, token, estado.config)
    return {'csrf': sessao.csrf, 'admin': sessao.admin and sessao.admin_fim > estado.sessoes.relogio(),
            'exige_2fa': estado.modo == 'oficial' or bool(estado.config.totp_segredo)}


@router.post('/api/admin/login')
async def login(dados: Credenciais, request: Request, response: Response,
                sessao=Depends(proteger_escrita)):
    """Valide credenciais com limite de tentativas e promova uma nova sessão."""
    estado = request.app.state
    ip = request.client.host if request.client else 'local'
    await asyncio.to_thread(estado.protecao_login.autenticar, ip, dados.usuario, dados.senha, dados.otp)
    return promover(request, response, sessao)


def promover(request, response, anterior):
    """Rotacione o cookie após login e conceda acesso administrativo por 30 minutos."""
    estado = request.app.state
    estado.sessoes.revogar(request.cookies.get('consultor'))
    token, sessao = estado.sessoes.criar()
    sessao.conversa = anterior.conversa
    sessao.admin, sessao.admin_fim = True, estado.sessoes.relogio() + 1800
    cookie(response, token, estado.config)
    return {'csrf': sessao.csrf, 'admin': True}


@router.post('/api/admin/logout')
async def logout(request: Request, response: Response, sessao=Depends(proteger_escrita)):
    """Revogue sessão administrativa, contexto e cookie da requisição."""
    estado = request.app.state
    estado.chatbot.limpar(sessao.conversa)
    estado.sessoes.revogar(request.cookies.get('consultor'))
    response.delete_cookie('consultor', path='/')
    return {'ok': True}


@router.delete('/api/sessao')
async def esquecer(request: Request, response: Response, sessao=Depends(proteger_escrita)):
    """Remova contexto e cookie da sessão solicitante; não opere sobre outras sessões."""
    request.app.state.chatbot.limpar(sessao.conversa)
    request.app.state.sessoes.revogar(request.cookies.get('consultor'))
    response.delete_cookie('consultor', path='/')
    return {'ok': True}
