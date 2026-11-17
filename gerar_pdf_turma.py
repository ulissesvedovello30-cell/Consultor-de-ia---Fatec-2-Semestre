"""Gera o PDF da turma a partir de um texto simples.

Uso (precisa de `pip install reportlab`, só para esta ferramenta):
    python gerar_pdf_turma.py
    python gerar_pdf_turma.py dados/outra_turma.txt

Formato do .txt: `# Título`, `## Seção` (só organiza o .txt, não vai pro PDF) e, no resto,
um fato por parágrafo (separados por linha em branco), cada um com tudo junto:
disciplina, data, horário e local. No PDF, cada fato vira um item de lista começando com
"-": é o hífen que deixa o RAG separar um fato do outro. Se a data ficar longe do nome da
prova, o bot erra.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_PASTA = Path(__file__).parent / "dados"


def gerar(origem: Path, destino: Path) -> None:
    estilos = getSampleStyleSheet()
    elementos = []

    for bloco in origem.read_text(encoding="utf-8").split("\n\n"):
        bloco = bloco.strip()
        if not bloco:
            continue
        if bloco.startswith("## "):
            continue  # um título de seção colaria no fato anterior depois da extração do texto
        if bloco.startswith("# "):
            elementos.append(Paragraph(escape(bloco[2:]), estilos["Heading1"]))
        else:
            # escape: o Paragraph do reportlab lê um mini-HTML, e "<" ou "&" quebrariam o texto
            fato = ParagraphStyle("fato", parent=estilos["BodyText"], leftIndent=14, bulletIndent=0)
            elementos += [Paragraph(escape(" ".join(bloco.split())), fato, bulletText="-"), Spacer(1, 0.25 * cm)]

    SimpleDocTemplate(str(destino), pagesize=A4, title=origem.stem, author="Fatec").build(elementos)


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else _PASTA / "turma_exemplo.txt"
    destino = origem.with_suffix(".pdf")
    gerar(origem, destino)
    print(f"PDF gerado: {destino}")
