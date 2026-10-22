"""Inspeção preventiva de documentos, executada dentro do processo de extração."""
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from dominio.erros import ErroIndexacao

PROIBIDOS_PDF = {'/JS', '/JavaScript', '/AA', '/OpenAction', '/Launch', '/EmbeddedFiles', '/RichMedia', '/XFA', '/AcroForm'}


def conferir_docx(caminho):
    """Recuse arquivos DOCX ambíguos, ativos, externos ou com expansão excessiva."""
    try:
        with ZipFile(caminho) as arquivo:
            conferir_catalogo(arquivo.infolist())
            for item in arquivo.infolist():
                conferir_item(arquivo, item)
    except (BadZipFile, RuntimeError, OSError, ValueError):
        raise ErroIndexacao('DOCX inválido ou protegido.') from None


def conferir_catalogo(itens):
    """Limite expansão e recuse nomes duplicados ou ausência do documento principal."""
    nomes = [i.filename for i in itens]
    if len(itens) > 3000 or sum(i.file_size for i in itens) > 50 * 1024 * 1024:
        raise ErroIndexacao('DOCX expandido excede o limite permitido.')
    if len(nomes) != len(set(nomes)) or 'word/document.xml' not in nomes:
        raise ErroIndexacao('Estrutura DOCX inválida ou ambígua.')


def conferir_item(arquivo, item):
    """Recuse caminhos, macros, objetos incorporados e relações externas no pacote."""
    nome = item.filename.lower()
    partes = PurePosixPath(nome).parts
    if nome.startswith('/') or '..' in partes or '\\' in nome or ':' in nome:
        raise ErroIndexacao('DOCX contém caminho não permitido.')
    if item.flag_bits & 1 or any(p in nome for p in ('vbaproject', '/embeddings/', '/activex/', 'afchunk')):
        raise ErroIndexacao('DOCX contém conteúdo ativo ou protegido.')
    if nome.endswith(('.rels', '.xml')):
        conferir_xml(arquivo.read(item), nome)


def conferir_xml(bruto, nome):
    """Recuse DTD, entidades e relações externas, inclusive XML UTF-16/32."""
    normal = bruto.replace(b'\x00', b'').lower()
    if b'<!doctype' in normal or b'<!entity' in normal:
        raise ErroIndexacao('DOCX contém declarações XML não permitidas.')
    if nome.endswith('.rels') and b'external' in normal:
        raise ErroIndexacao('DOCX contém relação externa. Remova vínculos ou envie TXT/PDF.')


def conferir_pdf(leitor):
    """Percorra referências do PDF sob limites e recuse ações ou anexos ativos."""
    fila, vistos = [leitor.trailer], set()
    while fila:
        objeto = resolver_objeto(fila.pop(), vistos)
        if len(vistos) > 50000:
            raise ErroIndexacao('PDF estruturalmente complexo demais.')
        if isinstance(objeto, dict):
            conferir_chaves_pdf(objeto)
            fila.extend(objeto.values())
        elif isinstance(objeto, (list, tuple)):
            fila.extend(objeto)


def resolver_objeto(objeto, vistos):
    """Resolva uma referência apenas uma vez para impedir ciclos no grafo PDF."""
    from pypdf.generic import IndirectObject
    if isinstance(objeto, IndirectObject):
        chave = (objeto.idnum, objeto.generation)
        if chave in vistos:
            return None
        vistos.add(chave)
        return objeto.get_object()
    return objeto


def conferir_chaves_pdf(objeto):
    """Recuse ações, formulários e anexos; esta inspeção não substitui antivírus."""
    if PROIBIDOS_PDF.intersection(objeto) or objeto.get('/S') in {'/JavaScript', '/Launch', '/SubmitForm', '/ImportData', '/GoToR'}:
        raise ErroIndexacao('PDF contém ação, formulário ou anexo não permitido.')
