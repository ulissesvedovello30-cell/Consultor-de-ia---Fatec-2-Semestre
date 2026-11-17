"""Reconhecimento de dúvidas frequentes, separado dos textos das respostas."""
import re
from aplicacao.servicos.recuperacao.linguagem.correcao import preparar_consulta

PADROES = {
    'mensalidade': r'mensalidade|gratuit|\bgratis\b|(?:custa|custo|pago|paga|pagar|preco|valor).*(?:curso|estudar|faculdade|mensal)|(?:curso|faculdade).*(?:custa|pago|paga|valor)',
    'horario': r'horarios?|turnos?|(?:que|quais) horas|hora (?:de entrada|de saida)|(?:aulas?|cursos?).*(?:manha|noite|tarde)',
    'modalidade': r'presencia[li]|presencialmente|\bead\b|online|on line|distancia|remot[oa]|assincron|hibrid|modalidade|precis.*(?:ir|comparecer).*(?:aula|faculdade)',
    'grade': r'grade|matriz curricular|(?:onde|acess|link|consult|ver).*(?:disciplinas|materias|matriz)',
    'nivel': r'nivel.*(?:curso|ensino)|(?:superior|tecnico|tecnologo|bacharelado)|(?:curso|formacao).*(?:tecnica|tecnologica)|(?:sao|considerados).*(?:graduacao)',
}
OUTROS = re.compile(r'biblioteca|secretaria|estagio|professor|restaurante|estacionamento|transferencia|trancamento|dependencia|estrangeir|bolsa|desconto')


def assuntos_frequentes(pergunta):
    """Reconheça propriedades usuais sem transformar uma condição nova em FAQ.

    Args:
        pergunta (str): Pergunta com ou sem curso explícito.

    Returns:
        set[str]: Assuntos reconhecidos; condições fora da FAQ seguem a busca geral.
    """
    texto = preparar_consulta(pergunta)
    if OUTROS.search(texto):
        return set()
    assuntos = {nome for nome, padrao in PADROES.items() if re.search(padrao, texto)}
    if re.search(r'vestibular|inscri|isencao|taxa|boleto|pagamento|matricula', texto):
        if not re.search(r'mensalidade|gratuit|gratis', texto):
            assuntos.discard('mensalidade')
        assuntos.discard('horario')
    return assuntos
