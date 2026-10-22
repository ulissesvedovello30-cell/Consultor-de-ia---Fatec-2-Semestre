import json
import re
from dataclasses import dataclass
from dominio.trecho_documento import TrechoDocumento

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
        if not isinstance(objeto, dict) or objeto.get('status') != 'respondida':
            return sem_resposta(melhor)
        return montar_afirmacoes(objeto, usados, melhor)
    except (ValueError, KeyError, TypeError, AttributeError):
        return sem_resposta(melhor)  # nunca acrescentar citações a texto inválido


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
