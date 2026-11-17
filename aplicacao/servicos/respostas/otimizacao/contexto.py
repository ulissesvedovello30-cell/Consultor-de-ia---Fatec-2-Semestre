"""Monte contexto curto, sem repetir evidências idênticas."""


def organizar_contexto(trechos, limite=8, caracteres=6000):
    """Selecione evidências completas dentro do orçamento do contexto.

    Args:
        trechos (list): Evidências já classificadas e aprovadas pela política.
        limite (int): Quantidade máxima de trechos.
        caracteres (int): Orçamento de texto, sem cortar passagens ao meio.

    Returns:
        list: Evidências únicas preservadas na ordem de relevância.
    """
    selecionados, total = [], 0
    for trecho in trechos:
        if len(selecionados) < limite and total + len(trecho.texto) <= caracteres and not repetido(trecho, selecionados):
            selecionados.append(trecho)
            total += len(trecho.texto)
    return selecionados


def repetido(trecho, selecionados):
    """Identifique repetição literal dentro do mesmo documento.

    Args:
        trecho: Evidência candidata ao contexto.
        selecionados (list): Evidências já escolhidas.

    Returns:
        bool: Indica duplicação textual literal no mesmo documento e curso.
    """
    texto = ' '.join(trecho.texto.split())
    return any(t.arquivo == trecho.arquivo and t.curso == trecho.curso and
               ' '.join(t.texto.split()) == texto for t in selecionados)


def descrever_trecho(numero, trecho):
    """Identifique o papel e o curso de cada evidência no contexto não confiável.

    Args:
        numero (int): Índice fornecido ao modelo.
        trecho: Evidência validada, com metadados de recuperação.

    Returns:
        str: Cabeçalho numerado e passagem original do documento.
    """
    curso = trecho.nome_curso or trecho.curso or 'geral'
    papel = trecho.tipo_info or 'passagem'
    cabecalho = f'[Trecho {numero} | Fonte: {trecho.rotulo} | Curso: {curso} | Papel: {papel}]'
    return cabecalho + '\n' + trecho.texto
