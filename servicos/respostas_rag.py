import json
import re
import logging
from dataclasses import dataclass
from dominio.trecho_documento import TrechoDocumento

logger = logging.getLogger(__name__)

SEM_RESPOSTA = ('Não encontrei essa informação nos documentos da faculdade. '
                'Tente reformular a pergunta ou procure a secretaria.')


@dataclass(frozen=True)
class RespostaRAG:
    texto: str
    fontes: tuple[TrechoDocumento, ...]
    encontrou: bool = True
    melhor_similaridade: float = 0.0
    fontes_no_texto: bool = False

    def texto_com_fontes(self):
        """Retorne a resposta com fontes, evitando repetir citações já presentes."""
        if not self.fontes or self.fontes_no_texto:
            return self.texto
        vistas = sorted({t.rotulo for t in self.fontes})
        return self.texto + '\n\nFontes:\n' + '\n'.join('- ' + x for x in vistas)


def sem_resposta(melhor=0.0):
    """Retorne uma resposta sem evidências, preservando a similaridade diagnóstica."""
    return RespostaRAG(SEM_RESPOSTA, (), False, melhor)


def validar_afirmacao(afirmacao, usados):
    """Valide texto, fontes e evidência integral; retorne frase e IDs sem repetição."""
    frase, ids = afirmacao['texto'], afirmacao['fontes']
    if not isinstance(frase, str) or not frase.strip() or len(frase) > 1200:
        raise ValueError('Afirmação inválida.')
    if not isinstance(ids, list) or not ids:
        raise ValueError('Referências ausentes.')
    if any(type(i) is not int or not 1 <= i <= len(usados) for i in ids):
        raise ValueError('Fonte inválida.')
    validar_evidencias(frase.strip(), ids, usados)
    return frase.strip(), list(dict.fromkeys(ids))


def montar_afirmacoes(objeto, usados, melhor):
    """Retorne resposta com fontes verificadas; lance ValueError para estrutura inválida."""
    afirmacoes = objeto['afirmacoes']
    if not isinstance(afirmacoes, list) or not 1 <= len(afirmacoes) <= 5:
        raise ValueError('Quantidade inválida.')
    validadas = [validar_afirmacao(a, usados) for a in afirmacoes]
    if sum(len(frase) for frase, ids in validadas) > 2400:
        raise ValueError('Resposta muito longa.')
    linhas = [frase + ' ' + ' '.join(f'[{usados[i-1].rotulo}]' for i in ids)
              for frase, ids in validadas]
    citados = sorted({i for frase, ids in validadas for i in ids})
    return RespostaRAG('\n\n'.join(linhas), tuple(usados[i-1] for i in citados), True, melhor, True)


def interpretar(bruto, usados, melhor):
    """Interprete JSON do gerador; recuse respostas inválidas sem inventar citações.
    
    Args:
        bruto: Saída textual não confiável do gerador.
        usados: Trechos recuperados disponíveis para citação.
        melhor: Maior similaridade observada; não representa confiança factual.
    
    Returns:
        RespostaRAG validada ou resultado de informação insuficiente.
    """
    try:
        texto = re.sub(r'^```(?:json)?\s*|\s*```$', '', (bruto or '').strip())
        objeto = json.loads(texto)
        return interpretar_objeto(objeto, usados, melhor)
    except (ValueError, KeyError, TypeError, AttributeError):
        logger.warning('rag_resposta_rejeitada motivo=estrutura_ou_evidencia_invalida')
        return sem_resposta(melhor)  # nunca acrescentar citações a texto inválido


def interpretar_objeto(objeto, usados, melhor):
    """Materialize referências do Gemini e mantenha o contrato extrativo anterior.

    Args:
        objeto (dict): Seleção estruturada recebida do gerador.
        usados (list): Trechos que o gerador realmente recebeu.
        melhor (float): Maior pontuação da recuperação.

    Returns:
        RespostaRAG: Evidências originais validadas ou informação insuficiente.
    """
    if not isinstance(objeto, dict) or objeto.get('status') != 'respondida':
        logger.info('rag_selecao_insuficiente')
        return sem_resposta(melhor)
    if 'trechos' in objeto:
        objeto = {'afirmacoes': afirmacoes_por_referencias(objeto['trechos'], usados)}
    return montar_afirmacoes(objeto, usados, melhor)


def afirmacoes_por_referencias(referencias, usados):
    """Recupere o texto no servidor sem pedir ao modelo que copie a formatação.

    Args:
        referencias (list[int]): Números dos trechos selecionados.
        usados (list): Evidências numeradas do contexto enviado.

    Returns:
        list[dict]: Textos integrais e referências verificadas.

    Raises:
        ValueError: Se algum identificador estiver fora do contexto.
    """
    if not isinstance(referencias, list) or not 1 <= len(referencias) <= 5:
        raise ValueError('Seleção de trechos inválida.')
    if any(type(i) is not int or not 1 <= i <= len(usados) for i in referencias):
        raise ValueError('Referência não fornecida ao gerador.')
    return [{'texto': usados[i - 1].texto.strip(), 'fontes': [i]}
            for i in dict.fromkeys(referencias)]


def validar_evidencias(frase, ids, usados):
    """Exija passagem literal em cada fonte citada, sem fabricar respaldo documental."""
    from servicos.politica import validar_publico
    validar_publico(frase)
    if any(frase not in passagens_completas(usados[i - 1].texto) for i in ids):
        raise ValueError('A afirmação não é uma passagem literal da fonte.')


def passagens_completas(texto):
    """Aceite apenas trecho inteiro, admitindo a remoção de um marcador de lista."""
    integral = texto.strip()
    return {integral, re.sub(r'^[-•–*]\s+', '', integral)}
