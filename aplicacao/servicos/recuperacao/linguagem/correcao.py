"""Correção restrita da consulta, sem alterar números ou o conteúdo das fontes."""
import re
from functools import lru_cache
from aplicacao.servicos.recuperacao.consulta_textual import EQUIVALENTES, IGNORADAS

VOCABULARIO = frozenset(('mensalidade mensalidades gratuito gratuitos gratuita gratuitas '
    'presencial presenciais presencialmente assincrona assincronas online distancia '
    'horario horarios duracao vestibular vestibulares inscricao inscricoes inscrever '
    'curso cursos curricular curriculares grade disciplinas materias semestre semestres '
    'superior superiores tecnico tecnicos tecnologia tecnologo graduacao faculdade fatec '
    'calendario recesso ferias inteligencia artificial sustentabilidade governanca '
    'secretaria biblioteca matricula prova exame custo custa custos quanto quais quando '
    'periodo prazo taxa taxas pagamento pagar isencao desconto professor professores '
    'gratuidade mensal noturno matutino vespertino horaria horarias quantos quantas').split())
PALAVRAS_COMUNS = frozenset((
    'grande grandes pegar prato pratos provar justo justa justos justas susto sustos '
    'pagas tacas busto curto curta cursa marca marco carta parte porta conta ponto '
    'mundo festa causa pausa carga datas notas media tempo local valor feira manha '
    'tarde noite matutina noturna vespertina exames aulas provas horas vagas turma '
    'turmas atual anual total final geral legal igual papel setor maior menor melhor '
    'autor fator motor reitor diretor trova brava crava grava trava canto campo banco '
    'plano bloco livro texto lista possa posso passo passa pensa pesar falar olhar '
    'andar entrar sair levar trazer fazer saber poder querer dever haver estar ficar '
    'deixar passar chegar voltar seguir pedir enviar mandar receber abrir fechar mudar '
    'trocar tirar gerar criar tomar ganhar perder achar viver morar trabalhar formar '
    'concluir terminar comecar iniciar acabar funcionar acontecer existir oferecer '
    'precisar conseguir informar explicar ajudar consultar acessar emitir solicitar '
    'entregar realizar participar apresentar comprovante declaracao historico diploma '
    'certificado carteira carteirinha trancamento transferencia aproveitamento '
    'frequencia aprovacao reprovacao monitoria iniciacao cientifica extensao pesquisa '
    'cantina estacionamento endereco localizacao campus unidade laboratorio bolsas '
    'auxilio intercambio regimento regulamento coordenacao coordenador diretoria '
    'faltas media notas dependencia'
).split())
PROTEGIDAS = VOCABULARIO | IGNORADAS | EQUIVALENTES.keys() | PALAVRAS_COMUNS
ABREVIACOES = {'q': 'que', 'oq': 'o que', 'qto': 'quanto', 'qnt': 'quanto',
               'qnts': 'quantos', 'qnd': 'quando', 'vc': 'voce', 'vcs': 'voces', 'eh': 'e'}


def preparar_consulta(texto):
    """Normalize a escrita apenas para interpretar a pergunta.

    Args:
        texto (str): Consulta que permanece sujeita à validação de segurança original.

    Returns:
        str: Consulta sem acentos, com abreviações e correções inequívocas.
    """
    from aplicacao.servicos.recuperacao.filtros_acervo import normalizar
    corrigida = re.sub(r'\b[a-z]+\b', lambda m: corrigir_palavra(m[0]), normalizar(texto))
    return re.sub(r'\b(quais|os|dos|nos|estes|esses)\s+([a-z]+)\b', ajustar_plural, corrigida)


def ajustar_plural(achado):
    """Use concordância explícita para resolver uma aproximação no plural.

    Args:
        achado: Quantificador plural e palavra seguinte identificados na consulta.

    Returns:
        str: Expressão com alternativa plural única ou a expressão original.
    """
    prefixo, palavra = achado.groups()
    if palavra in PROTEGIDAS or len(palavra) < 5:
        return achado[0]
    opcoes = [p for p in VOCABULARIO if p.endswith('s') and edicao_unica(palavra, p)]
    return prefixo + ' ' + opcoes[0] if len(opcoes) == 1 else achado[0]


@lru_cache(maxsize=2048)
def corrigir_palavra(palavra):
    """Corrija somente um erro de edição quando houver uma única alternativa.

    Args:
        palavra (str): Palavra minúscula sem acentos.

    Returns:
        str: Alternativa única ou a palavra original; siglas e números são preservados.
    """
    if palavra in ABREVIACOES:
        return ABREVIACOES[palavra]
    if palavra in PROTEGIDAS or not 5 <= len(palavra) <= 24:
        return palavra
    opcoes = [p for p in VOCABULARIO if edicao_unica(palavra, p)]
    return opcoes[0] if len(opcoes) == 1 else palavra


def edicao_unica(origem, destino):
    """Compare uma troca, inserção, remoção ou inversão de letras vizinhas.

    Args:
        origem (str): Palavra digitada.
        destino (str): Palavra do vocabulário institucional restrito.

    Returns:
        bool: Indica distância máxima de uma edição simples.
    """
    if len(origem) == len(destino):
        posicoes = [i for i, par in enumerate(zip(origem, destino)) if par[0] != par[1]]
        return len(posicoes) <= 1 or letras_invertidas(origem, destino, posicoes)
    menor, maior = sorted((origem, destino), key=len)
    return len(maior) == len(menor) + 1 and any(maior[:i] + maior[i+1:] == menor for i in range(len(maior)))


def letras_invertidas(origem, destino, posicoes):
    """Verifique uma inversão adjacente, sem aceitar duas trocas independentes.

    Args:
        origem (str): Palavra digitada.
        destino (str): Candidata do vocabulário.
        posicoes (list[int]): Posições que diferem.

    Returns:
        bool: Indica uma única inversão de letras adjacentes.
    """
    return len(posicoes) == 2 and posicoes[1] == posicoes[0] + 1 and all(
        origem[i] == destino[j] for i, j in zip(posicoes, reversed(posicoes)))
