"""PDF pequeno com texto legível para testar o processamento real de uploads."""
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject


def criar_pdf(texto):
    """Gere um PDF de uma página com a informação pública recebida."""
    escritor = PdfWriter()
    pagina = escritor.add_blank_page(width=595, height=842)
    fonte = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    pagina[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): fonte})})
    fluxo = DecodedStreamObject()
    seguro = texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    fluxo.set_data(f'BT /F1 12 Tf 30 790 Td ({seguro}) Tj ET'.encode('latin-1'))
    pagina[NameObject('/Contents')] = escritor._add_object(fluxo)
    destino = BytesIO(); escritor.write(destino)
    return destino.getvalue()
