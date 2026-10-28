"""Localize os documentos de uma pasta, para indexar vários de uma vez (inclusive os que forem chegando)."""
from pathlib import Path

FORMATOS = {'.pdf', '.docx', '.txt', '.xlsx'}


def documentos_da_pasta(pasta):
    """Liste os documentos aceitos da pasta, ignorando subpastas, temporários do Office e outros formatos."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted(c for c in pasta.iterdir()
                  if c.is_file() and c.suffix.lower() in FORMATOS and not c.name.startswith('~$'))


def expandir(caminhos):
    """Troque cada pasta pelos documentos dentro dela; mantenha os arquivos como estão."""
    return [arquivo for caminho in map(Path, caminhos)
            for arquivo in (documentos_da_pasta(caminho) if caminho.is_dir() else [caminho])]
