"""Caminhos absolutos independentes da pasta aberta no terminal."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCUMENTOS = RAIZ / 'documentos'
RUNTIME = RAIZ / 'runtime'
