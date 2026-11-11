import asyncio
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import Field
from web.esquemas import ModeloEstrito
from web.seguranca import proteger_escrita, limitar

router = APIRouter()


class Pergunta(ModeloEstrito):
    texto: str = Field(min_length=1, max_length=1500)


def fonte_json(trecho):
    """Retorne referência estruturada com link somente à fonte ativa no servidor."""
    return dict(arquivo=trecho.arquivo, pagina=trecho.pagina,
                similaridade=trecho.similaridade, url_oficial=trecho.url_oficial,
                url=f'/api/fontes/{trecho.documento_id}/{trecho.versao_id}')


@router.post('/api/chat')
async def perguntar(dados: Pergunta, request: Request, sessao=Depends(proteger_escrita)):
    """Processe consulta pública com limites globais e exclusão mútua por sessão.
    
    Args:
        dados: Entrada validada pelo esquema da rota.
        request: Requisição HTTP com estado e sessão do servidor.
        sessao: Sessão opaca validada pela dependência de segurança.
    
    Returns:
        Resposta HTTP com texto, fontes e estado.
    """
    estado = request.app.state
    limitar(request, 'chat', estado.limite_chat)
    if not estado.limite_global.permitir('global') or sessao.ocupada:
        raise HTTPException(429, 'Atendimento ocupado. Tente novamente em instantes.')
    sessao.ocupada = True
    try:
        resposta = await estado.chatbot.processar_mensagem(sessao.conversa, dados.texto)
    finally:
        sessao.ocupada = False
    return apresentar(resposta)


def apresentar(resposta):
    """Converta resultado de domínio em JSON e código HTTP consistente."""
    codigo = {'ocupado': 503, 'indisponivel': 503, 'prazo': 504, 'limite': 429, 'invalida': 422}
    from fastapi.responses import JSONResponse
    return JSONResponse(dict(texto=resposta.texto, sucesso=resposta.sucesso,
        estado=resposta.estado, similaridade=resposta.similaridade,
        fontes=[fonte_json(t) for t in resposta.fontes]), status_code=codigo.get(resposta.estado, 200))


@router.delete('/api/conversa')
async def limpar(request: Request, sessao=Depends(proteger_escrita)):
    """Remova o contexto temporário da conversa solicitante."""
    request.app.state.chatbot.limpar(sessao.conversa)
    return {'ok': True}


@router.get('/api/health')
async def health(request: Request):
    """Verifique disponibilidade do acervo sem expor configuração interna."""
    limitar(request, 'health', request.app.state.limite_chat)
    await asyncio.to_thread(request.app.state.base.carregar)
    return {'pronto': True, 'modo': request.app.state.modo}


@router.get('/api/fontes/{documento_id}/{versao_id}', response_class=PlainTextResponse)
async def fonte(documento_id: str, versao_id: str, request: Request):
    """Retorne o texto de uma versão ainda ativa ou informe ausência."""
    limitar(request, 'fonte', request.app.state.limite_chat)
    repo = request.app.state.base.repositorio
    linhas = await asyncio.to_thread(repo.fonte, documento_id, versao_id)
    if not linhas:
        raise HTTPException(404, 'Esta versão não está mais ativa.')
    return '\n\n'.join(f"Página {l['pagina'] or '—'}\n{l['texto']}" for l in linhas)


@router.get('/api/info')
async def informacoes(request: Request):
    """Retorne modo e identificação pública do responsável, nunca configurações secretas."""
    import os
    return {'modo': request.app.state.modo,
            'responsavel': os.getenv('PRIVACIDADE_RESPONSAVEL') or 'Responsável ainda não configurado',
            'contato': os.getenv('PRIVACIDADE_CONTATO') or 'Consulte a secretaria antes do uso oficial'}
