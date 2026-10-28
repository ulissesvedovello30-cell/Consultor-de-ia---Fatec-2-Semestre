"""Inspeção preventiva de documentos, executada dentro do processo de extração."""
from collections import namedtuple
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from dominio.erros import ErroIndexacao

Formato = namedtuple('Formato', 'rotulo principal proibidos')
DOCX = Formato('DOCX', 'word/document.xml', ('vbaproject', '/embeddings/', '/activex/', 'afchunk'))
XLSX = Formato('XLSX', 'xl/workbook.xml', ('vbaproject', '/embeddings/', '/activex/', 'afchunk',
                                           'externallinks', 'oleobject', '/connections.xml', 'ctrlprops'))
PROIBIDOS_PDF = {'/JS', '/JavaScript', '/AA', '/OpenAction', '/Launch', '/EmbeddedFiles', '/RichMedia', '/XFA', '/AcroForm'}


def conferir_docx(caminho):
    """Recuse arquivos DOCX ambíguos, ativos, externos ou com expansão excessiva."""
    conferir_pacote(caminho, DOCX)


def conferir_xlsx(caminho):
    """Recuse planilhas XLSX ambíguas, com macros, vínculos externos ou expansão excessiva."""
    conferir_pacote(caminho, XLSX)


def conferir_pacote(caminho, formato):
    """Inspecione o ZIP do documento Office sem interpretar o conteúdo dos arquivos internos."""
    try:
        with ZipFile(caminho) as arquivo:
            conferir_catalogo(arquivo.infolist(), formato)
            for item in arquivo.infolist():
                conferir_item(arquivo, item, formato)
    except (BadZipFile, RuntimeError, OSError, ValueError):
        raise ErroIndexacao(f'{formato.rotulo} inválido ou protegido.') from None


def conferir_catalogo(itens, formato=DOCX):
    """Limite expansão e recuse nomes duplicados ou ausência do documento principal."""
    nomes = [i.filename for i in itens]
    if len(itens) > 3000 or sum(i.file_size for i in itens) > 50 * 1024 * 1024:
        raise ErroIndexacao(f'{formato.rotulo} expandido excede o limite permitido.')
    if len(nomes) != len(set(nomes)) or formato.principal not in nomes:
        raise ErroIndexacao(f'Estrutura {formato.rotulo} inválida ou ambígua.')


def conferir_item(arquivo, item, formato=DOCX):
    """Recuse caminhos, macros, objetos incorporados e relações externas no pacote."""
    nome = item.filename.lower()
    partes = PurePosixPath(nome).parts
    if nome.startswith('/') or '..' in partes or '\\' in nome or ':' in nome:
        raise ErroIndexacao(f'{formato.rotulo} contém caminho não permitido.')
    if item.flag_bits & 1 or any(p in nome for p in formato.proibidos):
        raise ErroIndexacao(f'{formato.rotulo} contém conteúdo ativo ou protegido.')
    if nome.endswith(('.rels', '.xml')):
        conferir_xml(arquivo.read(item), nome, formato)


def conferir_xml(bruto, nome, formato=DOCX):
    """Recuse DTD, entidades e relações externas, inclusive XML UTF-16/32."""
    normal = bruto.replace(b'\x00', b'').lower()
    if b'<!doctype' in normal or b'<!entity' in normal:
        raise ErroIndexacao(f'{formato.rotulo} contém declarações XML não permitidas.')
    if nome.endswith('.rels') and b'external' in normal:
        raise ErroIndexacao(f'{formato.rotulo} contém relação externa. Remova vínculos ou envie TXT/PDF.')


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
