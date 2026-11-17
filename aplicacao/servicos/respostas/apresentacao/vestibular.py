"""Apresentação do ingresso e do prazo publicado em campos separados."""
import re
from aplicacao.servicos.recuperacao.calendario.edicoes import edicao_evento


def texto_inscricao(frase):
    """Identifique a edição e mantenha previsão, prorrogação e condições publicadas.

    Args:
        frase (str): Evento integral que já passou pela validação de evidência.

    Returns:
        str: Edição e prazo explícitos, ou a frase intacta quando não identificável.
    """
    ano, semestre = edicao_evento(frase)
    if not ano:
        return frase
    data, _, descricao = [p.strip() for p in frase.lstrip('- ').partition(':')]
    descricao = re.sub(r'^Previsão do período de Inscrições para o Vestibular do [12]º semestre de 20\d{2}',
                       'Período previsto de inscrições', descricao, flags=re.I)
    descricao = re.sub(r'^Inscrições para o Vestibular do [12]º semestre de 20\d{2}', 'Inscrições', descricao, flags=re.I)
    return f'Ingresso no {semestre}º semestre de {ano}:\n{data}.\n{descricao}'
