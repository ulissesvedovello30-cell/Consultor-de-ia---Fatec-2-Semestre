"""Defesa em camadas; padrões preventivos não são um detector universal de dados pessoais."""
import re
from aplicacao.servicos.recuperacao.filtros_acervo import normalizar, expandir_cursos

PESSOAIS = re.compile(
    r'\b\d{3}[. ]?\d{3}[. ]?\d{3}[- ]?\d{2}\b|'
    r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b|'
    r'(?<!\d)(?:\+55\s*)?\(?\d{2}\)?[ -]?9?\d{4}[ -]?\d{4}(?!\d)|'
    r'\b(?:cpf|rg|ra|senha|password|prontuario)\s*[:=]\s*\S+', re.I)
INJECAO = re.compile(
    r'(ignore|disregard|esqueca|desconsidere).{0,80}(instru|prompt|regras|previous|system)|'
    r'(revele|mostre|reveal|show).{0,50}(system prompt|prompt do sistema|chave api|api key)|'
    r'\b(jailbreak|developer mode|modo desenvolvedor)\b|'
    r'<\|(?:system|im_start|im_end)\|>|\[INST\]', re.I | re.S)
ESCOPO = re.compile(
    r'\b(fatec|faculdade|academi\w*|universi\w*|secretaria|matricula|rematricula|'
    r'gradua\w*|tecnologo\w*|recesso\w*|receso|feriado\w*|inscri\w*|hackathon|matriz|ementa\w*|'
    r'calendario|prova\w*|aula\w*|curso\w*|turma\w*|semestre\w*|periodo|'
    r'prazo|integraliza\w*|modalidade|dura(?:r|m)?|conclusao|'
    r'mensalidade|gratuit\w*|duracao|presencia\w*|ia|esg|biblioteca|estagio|tcc|documento\w*|declaracao|edital|vestibular|'
    r'evento\w*|feira|horario|sala\w*|professor\w*|disciplina\w*|ferias|'
    r'enrollment|exam\w*|class\w*|calendar|library|college|internship|'
    r'isso|disso|esse|essa|quando|onde|when|where)\b', re.I)


class EntradaRecusada(ValueError):
    """Entrada incompatível com o atendimento público; mensagem segura ao usuário."""


def validar_publico(texto):
    """Recuse padrões pessoais e comandos maliciosos antes de enviar texto ao provedor."""
    if PESSOAIS.search(texto):
        raise EntradaRecusada('Remova CPF, RA, telefone, e-mail e outros dados pessoais antes de enviar.')
    if INJECAO.search(normalizar(texto)):
        raise EntradaRecusada('Envie uma dúvida sobre informações públicas da faculdade, sem instruções ao sistema.')
    return texto


def validar_pergunta(texto):
    """Valide texto público e peça contexto institucional quando o assunto não é reconhecido."""
    from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta
    from aplicacao.servicos.recuperacao.perguntas.assuntos import assuntos_frequentes
    validar_publico(texto)
    if not ESCOPO.search(expandir_cursos(preparar_consulta(texto))) and not assuntos_frequentes(texto):
        raise EntradaRecusada('Atendo assuntos públicos da faculdade. Informe o curso, evento ou serviço sobre o qual deseja saber.')
    return texto


def validar_documento(texto):
    """Recuse documento suspeito antes da gravação e dos embeddings remotos."""
    from aplicacao.dominio.erros import ErroIndexacao
    try:
        return validar_publico(texto)
    except EntradaRecusada as erro:
        raise ErroIndexacao('Documento não publicado: revise dados pessoais e instruções suspeitas. ' + str(erro)) from None
