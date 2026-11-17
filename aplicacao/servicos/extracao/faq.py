"""Mantenha cada pergunta da secretaria como uma unidade documental independente."""
import re


def separar_faq(caminho, paginas):
    """Separe os blocos antes do fatiamento, sem misturar assuntos ou cursos.

    Args:
        caminho (Path): Documento em processamento.
        paginas (list): Texto validado extraído da fonte.

    Returns:
        list: Blocos completos da FAQ ou páginas originais para outros documentos.
    """
    if caminho.name != 'FAQ_secretaria.txt':
        return paginas
    return [(pagina, bloco.strip()) for pagina, texto in paginas
            for bloco in re.split(r'(?m)(?=^Assunto:)', texto) if bloco.strip()]
