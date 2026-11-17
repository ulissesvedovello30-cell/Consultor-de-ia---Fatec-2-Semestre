"""Leitura dos campos da FAQ, sempre a partir do conteúdo ativo no banco."""
import re
from dataclasses import replace


def campo_faq(texto, nome):
    """Leia um campo de identificação da fonte institucional.

    Args:
        texto (str): Bloco original da FAQ.
        nome (str): Campo definido pelo aplicativo.

    Returns:
        str: Conteúdo publicado ou vazio quando ausente.
    """
    achado = re.search(r'^' + re.escape(nome) + r':\s*(.+)$', texto, re.M)
    return achado[1].strip() if achado else ''


def ficha_faq(trecho, assuntos, cursos):
    """Recorte a resposta correspondente, preservando sua versão e ressalvas.

    Args:
        trecho: Bloco de uma fonte ativa.
        assuntos (set[str]): Propriedades reconhecidas na consulta.
        cursos (set[str]): Cursos pedidos; vazio abrange os cursos da fonte.

    Returns:
        TrechoDocumento | None: Evidência literal ou ausência de correspondência.
    """
    assunto, curso = campo_faq(trecho.texto, 'Assunto'), campo_faq(trecho.texto, 'Curso')
    if trecho.arquivo != 'FAQ_secretaria.txt' or assunto not in assuntos or (curso and cursos and curso not in cursos):
        return None
    resposta = trecho.texto.partition('Resposta:')[2].strip()
    if not resposta:
        return None
    curso = curso or (next(iter(cursos)) if len(cursos) == 1 else '')
    return replace(trecho, texto=resposta, curso=curso, similaridade=1.0,
                   tipo_info='faq:' + assunto, grupo_resposta='consulta:faq')
