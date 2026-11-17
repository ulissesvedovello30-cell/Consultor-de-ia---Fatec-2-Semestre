import asyncio
import re
import unicodedata
import shutil
import tempfile
import zipfile
import time
from servicos.prazo import FIM
from pathlib import Path
from fastapi import HTTPException
from dominio.erros import ErroIndexacao


def validar_nome(nome):
    """Recuse nomes com caminhos, caracteres inválidos ou extensões não suportadas."""
    if not nome or len(nome) > 200 or re.search(r'[\\/\x00-\x1f]', nome):
        raise HTTPException(422, 'Nome de arquivo inválido.')
    if re.search(r'[:*?"<>|]', nome) or nome.endswith((' ', '.')):
        raise HTTPException(422, 'Nome incompatível com o sistema de arquivos.')
    if Path(nome).suffix.lower() not in {'.pdf', '.docx', '.txt'}:
        raise HTTPException(415, 'Envie PDF, DOCX ou TXT.')
    conferir_nome_portavel(nome)
    return nome


async def salvar_stream(request, destino, limite):
    """Grave arquivo temporário com limite de bytes e rejeite conteúdo vazio."""
    total = 0
    with destino.open('wb') as arquivo:
        async for parte in request.stream():
            total += len(parte)
            if total > limite:
                raise HTTPException(413, 'Arquivo excede 25 MB.')
            arquivo.write(parte)
    if not total:
        raise HTTPException(422, 'Arquivo vazio.')


def validar_conteudo(caminho):
    """Verifique assinatura PDF, estrutura DOCX ou ausência de bytes binários no TXT."""
    if caminho.suffix.lower() == '.pdf' and not caminho.read_bytes()[:1024].lstrip().startswith(b'%PDF-'):
        raise ErroIndexacao('O arquivo não contém um PDF válido.')
    if caminho.suffix.lower() == '.docx':
        validar_docx(caminho)
    if caminho.suffix.lower() == '.txt' and b'\x00' in caminho.read_bytes():
        raise ErroIndexacao('TXT contém dados binários.')


def validar_docx(caminho):
    """Recuse ZIP inválido, expansão excessiva ou ausência de estrutura DOCX."""
    try:
        with zipfile.ZipFile(caminho) as arquivo:
            infos = arquivo.infolist()
            if sum(i.file_size for i in infos) > 50 * 1024 * 1024 or len(infos) > 3000:
                raise ErroIndexacao('DOCX expandido excede o limite permitido.')
            if 'word/document.xml' not in arquivo.namelist():
                raise ErroIndexacao('DOCX inválido.')
    except zipfile.BadZipFile as erro:
        raise ErroIndexacao('DOCX inválido.') from erro


async def receber_upload(request, nome, metadados):
    """Reserve capacidade e receba upload; remova temporários em caso de falha."""
    estado = request.app.state
    if not estado.upload_vaga.acquire(blocking=False):
        raise HTTPException(503, 'Outro documento está sendo processado.')
    pasta = Path(tempfile.mkdtemp(prefix='consultor-upload-'))
    try:
        await salvar_stream(request, pasta / nome, estado.config.max_upload)
    except BaseException:
        finalizar_upload(estado, pasta)
        raise
    return await processar_em_thread(estado, pasta, nome, metadados)


def indexar_upload(estado, pasta, nome, metadados):
    """Indexe arquivo validado sob prazo e remova temporários ao concluir."""
    token = FIM.set(time.monotonic() + 300)
    try:
        validar_conteudo(pasta / nome)
        total = estado.base.indexar_arquivo(pasta / nome, forcar=True, metadados=metadados)
        return {'estado': 'indexado', 'trechos': total, 'nome': nome}
    finally:
        FIM.reset(token)
        finalizar_upload(estado, pasta)


def finalizar_upload(estado, pasta):
    """Remova diretório temporário e libere a vaga de indexação."""
    shutil.rmtree(pasta, ignore_errors=True)
    estado.upload_vaga.release()


def consumir_excecao(tarefa):
    """Consuma a exceção da tarefa concluída para evitar logs de dados internos."""
    if not tarefa.cancelled():
        tarefa.exception()


async def processar_em_thread(estado, pasta, nome, metadados):
    """Preserve a ocupação e limpeza da tarefa mesmo se o navegador desconectar."""
    tarefa = asyncio.create_task(asyncio.to_thread(indexar_upload, estado, pasta, nome, metadados))
    tarefa.add_done_callback(consumir_excecao)
    return await asyncio.shield(tarefa)


def conferir_nome_portavel(nome):
    """Recuse caracteres invisíveis e nomes de dispositivo reservados no Windows."""
    reservados = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}
    if any(unicodedata.category(c).startswith('C') for c in nome) or nome.split('.')[0].upper() in reservados:
        raise HTTPException(422, 'Nome de arquivo não permitido.')
