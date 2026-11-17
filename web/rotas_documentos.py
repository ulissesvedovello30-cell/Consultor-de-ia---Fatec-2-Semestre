import asyncio
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from dominio.metadados import Metadados
from web.seguranca import exigir_admin, admin_escrita, limitar
from web.uploads import receber_upload, validar_nome

router = APIRouter(prefix='/api/admin/documentos')


@router.get('')
async def listar(request: Request, admin=Depends(exigir_admin)):
    """Retorne documentos publicados e metadados de suas versões ativas."""
    return await asyncio.to_thread(request.app.state.base.repositorio.listar)


@router.post('')
async def adicionar(request: Request, nome: str = Query(max_length=200),
                    curso: str = Query('', max_length=160), periodo: str = Query('', max_length=80),
                    ano: int | None = None, inicio: date | None = None, fim: date | None = None,
                    url_oficial: str = Query('', max_length=1000), publico: bool = False, admin=Depends(admin_escrita)):
    """Exija revisão pública e autorização antes de receber e indexar um documento."""
    if not publico:
        raise HTTPException(422, 'Confirme a revisão do documento para publicação pública.')
    limitar(request, 'upload', request.app.state.limite_upload)
    meta = criar_metadados(curso, periodo, ano, inicio, fim, url_oficial)
    return await receber_upload(request, validar_nome(nome), meta)


def criar_metadados(curso, periodo, ano, inicio, fim, url_oficial):
    """Valide metadados públicos e converta falhas em erro HTTP 422."""
    from servicos.politica import validar_publico
    try:
        validar_publico(' '.join((curso, periodo, url_oficial)))
        return Metadados(curso, periodo, ano, inicio, fim, url_oficial)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


@router.delete('/{documento_id}')
async def excluir(documento_id: str, request: Request, admin=Depends(admin_escrita)):
    """Remova o documento e suas versões, mantendo atomicidade da operação."""
    return await asyncio.to_thread(excluir_do_acervo, request.app.state, documento_id)


def excluir_do_acervo(estado, documento_id):
    """Exclua sob a mesma trava dos uploads, impedindo republicação concorrente local."""
    if not estado.upload_vaga.acquire(blocking=False):
        raise HTTPException(503, 'Aguarde o processamento do documento antes de excluir.')
    try:
        if not estado.base.repositorio.excluir(documento_id):
            raise HTTPException(404, 'Documento não encontrado no acervo.')
        estado.base.carregar()
        return {'estado': 'excluido'}
    finally:
        estado.upload_vaga.release()
