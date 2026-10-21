import logging
import re
from pathlib import Path

from dominio.erros import ErroIndexacao

logger = logging.getLogger(__name__)

_MIN_CARACTERES_PAGINA = 30  # abaixo disso a página provavelmente é imagem (precisa de OCR)
_ITEM_DE_LISTA = re.compile(r"[•\-–*]\s")

# (número da página ou None, texto). DOCX e TXT não têm páginas.
Pagina = tuple[int | None, str]


def extrair_paginas(caminho: Path) -> list[Pagina]:
    """Extrai o texto do arquivo (.pdf, .docx ou .txt), página por página quando existe."""
    extrator = _EXTRATORES.get(caminho.suffix.lower())
    if extrator is None:
        aceitos = ", ".join(sorted(_EXTRATORES))
        raise ErroIndexacao(f"Formato '{caminho.suffix or '(sem extensão)'}' não suportado. Aceitos: {aceitos}.")
    return extrator(caminho)


def _extrair_pdf(caminho: Path) -> list[Pagina]:
    from pypdf import PdfReader  # import tardio: só quem indexa precisa da biblioteca

    try:
        leitor = PdfReader(caminho)
        paginas_pdf = list(leitor.pages)
    except Exception as e:
        raise ErroIndexacao(f"Não foi possível ler o PDF '{caminho.name}'") from e

    paginas: list[Pagina] = []
    sem_texto: list[int] = []

    for numero, pagina in enumerate(paginas_pdf, start=1):
        try:
            texto = pagina.extract_text() or ""
        except Exception:
            logger.warning("Falha ao extrair a página %d de '%s'", numero, caminho.name, exc_info=True)
            texto = ""

        texto = re.sub(r"-\s*\n\s*(\w)", r"\1", texto)  # junta palavras quebradas com hífen no fim da linha
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto).strip()

        if len(texto) < _MIN_CARACTERES_PAGINA:
            sem_texto.append(numero)
        if texto:
            paginas.append((numero, texto))

    if sem_texto:
        logger.warning(
            "'%s': páginas sem texto extraível (podem precisar de OCR): %s",
            caminho.name,
            sem_texto[:20],
        )
    if not paginas:
        raise ErroIndexacao(f"'{caminho.name}' não tem texto extraível (PDF digitalizado? precisa de OCR)")

    return paginas


def _extrair_txt(caminho: Path) -> list[Pagina]:
    try:
        bruto = caminho.read_bytes()
    except OSError as e:
        raise ErroIndexacao(f"Não foi possível ler o TXT '{caminho.name}'") from e

    for codificacao in ("utf-8-sig", "cp1252"):  # cp1252: bloco de notas antigo do Windows
        try:
            texto = "\n".join(bruto.decode(codificacao).splitlines()).strip()  # \r\n, \r e \n viram \n
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ErroIndexacao(f"Codificação não reconhecida em '{caminho.name}'")

    if not texto:
        raise ErroIndexacao(f"'{caminho.name}' está vazio")
    return [(None, texto)]


def _extrair_docx(caminho: Path) -> list[Pagina]:
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        documento = docx.Document(str(caminho))
    except ImportError as e:
        raise ErroIndexacao("A biblioteca python-docx não está instalada.") from e
    except Exception as e:
        raise ErroIndexacao(f"Não foi possível ler o DOCX '{caminho.name}'") from e

    blocos: list[str] = []
    # Percorre o corpo na ordem do documento, para a tabela (um calendário, por exemplo)
    # ficar junto do texto que a cerca.
    for elemento in documento.element.body.iterchildren():
        etiqueta = elemento.tag.rsplit("}", 1)[-1]
        if etiqueta == "p":
            texto = Paragraph(elemento, documento).text.strip()
            if texto:
                blocos.append(texto)
        elif etiqueta == "tbl":
            for linha in Table(elemento, documento).rows:
                celulas = [c.text.strip() for c in linha.cells]
                if any(celulas):
                    # "- " na frente: cada linha da tabela é um fato e não se cola nas vizinhas
                    blocos.append("- " + " | ".join(celulas))

    if not blocos:
        raise ErroIndexacao(f"'{caminho.name}' não tem texto")
    return [(None, "\n\n".join(blocos))]


_EXTRATORES = {".pdf": _extrair_pdf, ".txt": _extrair_txt, ".docx": _extrair_docx}


def dividir_em_trechos(texto: str, tamanho: int = 450, sobreposicao: int = 75) -> list[str]:
    """Agrupa parágrafos até `tamanho` caracteres; parágrafo maior que isso é fatiado com sobreposição.

    O padrão (450) cabe nos 128 tokens do modelo de embeddings: texto além do limite do
    modelo é cortado antes de virar vetor, e o trecho passaria a "esquecer" o final.
    """
    if tamanho <= 0 or not 0 <= sobreposicao < tamanho:
        # sobreposicao >= tamanho faria o fatiamento nunca avançar (loop infinito)
        raise ValueError("Configuração inválida: use tamanho > 0 e 0 <= sobreposicao < tamanho.")

    # O pypdf devolve parágrafos de PDF colados, sem linha em branco entre eles. Item de
    # lista (•, -, – ou *) também começa um parágrafo novo; senão o fatiamento cortaria
    # fatos no meio. Separar demais é inofensivo: os parágrafos voltam a ser juntados
    # abaixo, até o limite de `tamanho`.
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[•\-–*]\s)", texto) if p.strip()]
    trechos: list[str] = []
    atual = ""

    for paragrafo in paragrafos:
        if _ITEM_DE_LISTA.match(paragrafo) and atual:
            # Cada item de lista é um fato: colar dois no mesmo trecho misturaria as datas.
            trechos.append(atual)
            atual = ""

        if len(paragrafo) > tamanho:
            if atual:
                trechos.append(atual)
                atual = ""
            inicio = 0
            while inicio < len(paragrafo):
                fatia = paragrafo[inicio : inicio + tamanho].strip()
                if fatia:
                    trechos.append(fatia)
                inicio += tamanho - sobreposicao
            continue

        candidato = f"{atual}\n\n{paragrafo}" if atual else paragrafo
        if len(candidato) <= tamanho:
            atual = candidato
        else:
            trechos.append(atual)
            atual = paragrafo

    if atual:
        trechos.append(atual)
    return trechos
