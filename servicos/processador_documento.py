import re
from pathlib import Path
from dominio.erros import ErroIndexacao

ITEM = re.compile(r'[•\-–*]\s')


def extrair_paginas(caminho: Path):
    """Retorne pares de página e texto; recuse formato inválido ou conteúdo excessivo."""
    extratores = {'.pdf': extrair_pdf, '.docx': extrair_docx, '.txt': extrair_txt}
    try:
        paginas = extratores[caminho.suffix.lower()](caminho)
    except KeyError:
        raise ErroIndexacao('Formato não suportado. Aceitos: PDF, DOCX, TXT.') from None
    except (OSError, ValueError) as erro:
        raise ErroIndexacao('Não foi possível ler o documento.') from erro
    if sum(len(texto) for pagina, texto in paginas) > 2_000_000:
        raise ErroIndexacao('Documento excede dois milhões de caracteres. Divida o arquivo.')
    return paginas


def abrir_pdf(caminho):
    """Abra PDF legível e limitado a 300 páginas; lance ErroIndexacao em falhas."""
    from pypdf import PdfReader
    try:
        leitor = PdfReader(caminho)
        if leitor.is_encrypted or len(leitor.pages) > 300:
            raise ErroIndexacao('PDF protegido ou com mais de 300 páginas.')
        return validar_pdf(leitor)
    except ErroIndexacao:
        raise
    except Exception as erro:
        raise ErroIndexacao('Não foi possível ler o PDF.') from erro


def texto_pdf(pagina):
    """Extraia e normalize texto de uma página; retorne vazio se a extração falhar."""
    try:
        texto = pagina.extract_text() or ''
    except Exception:
        return ''
    texto = re.sub(r'-\s*\n\s*(\w)', r'\1', texto)
    return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]+', ' ', texto)).strip()


def extrair_pdf(caminho):
    """Retorne páginas de texto; recuse leitura parcial que demande OCR."""
    leitor = abrir_pdf(caminho)
    paginas = [(i, texto_pdf(p)) for i, p in enumerate(leitor.pages, 1)]
    suspeitas = [i for i, texto in paginas if len(texto) < 30]
    if suspeitas:
        lista = ', '.join(map(str, suspeitas[:20]))
        raise ErroIndexacao(f'Leitura incompleta nas páginas {lista}. Aplique OCR e envie novamente; nada foi atualizado.')
    if not paginas:
        raise ErroIndexacao('PDF vazio.')
    return paginas


def decodificar(bruto):
    """Decodifique bytes como UTF-8 ou CP1252; lance ErroIndexacao em falha."""
    for codificacao in ('utf-8-sig', 'cp1252'):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroIndexacao('Codificação do TXT não reconhecida.')


def extrair_txt(caminho):
    """Retorne o texto de um arquivo não vazio, sem número de página."""
    texto = '\n'.join(decodificar(caminho.read_bytes()).splitlines()).strip()
    if not texto:
        raise ErroIndexacao('Arquivo vazio.')
    return [(None, texto)]


def abrir_docx(caminho):
    """Abra um DOCX ou converta falhas de leitura em ErroIndexacao."""
    try:
        import docx
        return docx.Document(str(caminho))
    except Exception as erro:
        raise ErroIndexacao('Não foi possível ler o DOCX. Confira o arquivo e python-docx.') from erro


def blocos_docx(documento):
    """Produza parágrafos e linhas de tabelas na ordem original do DOCX."""
    from docx.text.paragraph import Paragraph
    for elemento in documento.element.body.iterchildren():
        etiqueta = elemento.tag.rsplit('}', 1)[-1]
        if etiqueta == 'p':
            yield Paragraph(elemento, documento).text.strip()
        elif etiqueta == 'tbl':
            yield from linhas_tabela(elemento, documento)


def extrair_docx(caminho):
    """Retorne texto não vazio de um DOCX, incluindo tabelas."""
    blocos = [b for b in blocos_docx(abrir_docx(caminho)) if b]
    if not blocos:
        raise ErroIndexacao('DOCX não tem texto.')
    return [(None, '\n\n'.join(blocos))]


def dividir_em_trechos(texto, tamanho=450, sobreposicao=75):
    """Pré-agrupamento por caracteres; o embedder aplica depois seu limite de tokens."""
    if tamanho <= 0 or not 0 <= sobreposicao < tamanho:
        raise ValueError('Use tamanho > 0 e 0 <= sobreposicao < tamanho.')
    paragrafos = [p.strip() for p in re.split(r'\n\s*\n|\n(?=[•\-–*]\s)', texto) if p.strip()]
    trechos, atual = [], ''
    for paragrafo in paragrafos:
        atual = agrupar(trechos, atual, paragrafo, tamanho, sobreposicao)
    if atual:
        trechos.append(atual)
    return trechos


def agrupar(trechos, atual, paragrafo, tamanho, sobreposicao):
    """Acrescente trechos completos à lista e retorne o fragmento ainda em montagem."""
    candidato = f'{atual}\n\n{paragrafo}' if atual else paragrafo
    separar = ITEM.match(paragrafo) or len(candidato) > tamanho
    if atual and separar:
        trechos.append(atual)
        candidato = paragrafo
    if len(paragrafo) > tamanho:
        trechos.extend(fatiar(paragrafo, tamanho, sobreposicao))
        return ''
    return candidato


def linhas_tabela(elemento, documento):
    """Produza linhas não vazias de uma tabela DOCX na ordem original."""
    from docx.table import Table
    for linha in Table(elemento, documento).rows:
        celulas = [c.text.strip() for c in linha.cells]
        if any(celulas):
            yield '- ' + ' | '.join(celulas)


def fatiar(texto, tamanho, sobreposicao):
    """Retorne fatias sobrepostas sem descartar o final do parágrafo."""
    return [p.strip() for i in range(0, len(texto), tamanho - sobreposicao)
            if (p := texto[i:i + tamanho]).strip()]


def validar_pdf(leitor):
    """Inspecione conteúdo ativo e retorne o leitor aprovado para extração."""
    from seguranca.arquivos import conferir_pdf
    conferir_pdf(leitor)
    return leitor
