"""Worker descartável: extração limitada, sem importar configuração de credenciais."""
import json
import os
import sys
from pathlib import Path
from dominio.erros import ErroIndexacao


def limitar_recursos():
    """Aplique cotas POSIX; no Windows o processo pai impõe apenas o prazo."""
    if os.name != 'posix':
        return
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def processar(caminho):
    """Valide estrutura e extraia páginas; retorne apenas erro público ou conteúdo."""
    from seguranca.arquivos import conferir_docx
    from servicos.processador_documento import extrair_paginas
    try:
        if caminho.suffix.lower() == '.docx':
            conferir_docx(caminho)
        return {'paginas': extrair_paginas(caminho)}
    except ErroIndexacao as erro:
        return {'erro': str(erro)}


def main():
    """Processe os caminhos fornecidos pelo pai e escreva resultado em arquivo privado."""
    limitar_recursos()
    resultado = processar(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(resultado, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
