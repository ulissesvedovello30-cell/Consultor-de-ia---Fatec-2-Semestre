"""Execute parsers complexos fora do processo HTTP, com prazo e saída limitados."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from dominio.erros import ErroIndexacao


def extrair_protegido(caminho):
    """Retorne páginas extraídas; encerre PDF/DOCX que excedam 20 segundos.

    Args:
        caminho: Arquivo local previamente recebido e limitado a 25 MB.

    Returns:
        Lista de pares de página e texto, sem executar conteúdo do documento.

    Raises:
        ErroIndexacao: Arquivo inválido, parser encerrado ou prazo excedido.
    """
    from servicos.processador_documento import extrair_paginas
    if caminho.stat().st_size > 25 * 1024 * 1024:
        raise ErroIndexacao('Arquivo excede 25 MB.')
    if caminho.suffix.lower() not in {'.pdf', '.docx'}:
        return extrair_paginas(caminho)
    with tempfile.TemporaryDirectory(prefix='consultor-parser-') as pasta:
        saida = Path(pasta) / 'resultado.json'
        executar(caminho, saida)
        return ler_resultado(saida)


def ambiente_minimo():
    """Monte ambiente do subprocesso sem copiar chaves de API ou credenciais."""
    ambiente = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
    ambiente['PYTHONPATH'] = os.pathsep.join(str(Path(p).resolve()) for p in sys.path if p)
    ambiente['PYTHONIOENCODING'] = 'utf-8'
    return ambiente


def executar(caminho, saida):
    """Execute worker sem shell; mate-o ao exceder prazo e sanitize erros do parser."""
    comando = [sys.executable, '-m', 'seguranca.worker_documento', str(caminho.resolve()), str(saida)]
    try:
        subprocess.run(comando, cwd=saida.parent, env=ambiente_minimo(), timeout=20, check=True,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError):
        raise ErroIndexacao('Extração recusada: arquivo inválido ou limite de recursos excedido.') from None


def ler_resultado(saida):
    """Leia resultado local limitado e converta falhas sem revelar detalhes internos."""
    try:
        if saida.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('Saída excessiva.')
        resultado = json.loads(saida.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ErroIndexacao('Resultado de extração inválido.') from None
    if 'erro' in resultado:
        raise ErroIndexacao(resultado['erro'])
    return [(pagina, texto) for pagina, texto in resultado['paginas']]
