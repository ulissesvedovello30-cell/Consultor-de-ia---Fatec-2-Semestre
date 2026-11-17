"""Índice invertido em memória, derivado somente das versões ativas no SQLite."""
from collections import defaultdict
from dataclasses import replace
from math import log
from aplicacao.servicos.recuperacao.linguagem.normalizacao import radical, radicais, aproximar


class IndiceLinguistico:
    """Recupere flexões portuguesas e mantenha o índice coerente com o acervo.

    O estado interno mantém a assinatura, os radicais e as posições das evidências.
    """

    def __init__(self):
        """Inicialize um índice vazio, sem modelos locais nem acesso remoto."""
        self._assinatura, self._textos, self._postagens = (), [], {}
        self._vocabulario = ()

    def atualizar(self, textos):
        """Reconstrua somente quando mudar uma evidência ou seu metadado.

        Args:
            textos (list): Snapshot vigente carregado do repositório.
        """
        assinatura = tuple((t.versao_id, t.texto, t.curso, t.periodo, t.ano) for t in textos)
        if assinatura == self._assinatura:
            return
        postagens = defaultdict(set)
        for i, trecho in enumerate(textos):
            for palavra in radicais(trecho.texto):
                postagens[palavra].add(i)
        self._assinatura, self._textos, self._postagens = assinatura, textos, dict(postagens)
        self._vocabulario = tuple(sorted(postagens))

    def buscar(self, palavras, cursos=(), limite=200):
        """Classifique candidatos por cobertura ponderada dos radicais da consulta.

        Args:
            palavras (set): Termos de conteúdo, sem os cursos usados como filtro.
            cursos (set): Cursos explicitamente pedidos.
            limite (int): Número máximo de candidatos.

        Returns:
            list: Trechos ativos com pontuação entre zero e um.
        """
        consulta = {self._resolver(radical(p)) for p in sorted(palavras)[:40]}
        pesos = {p: self._peso(p) for p in consulta}
        posicoes = set().union(*(self._postagens.get(p, set()) for p in consulta))
        candidatos = [self._pontuar(i, pesos) for i in posicoes if self._permitido(i, cursos)]
        return sorted(candidatos, key=lambda t: t.similaridade, reverse=True)[:limite]

    def _resolver(self, palavra):
        """Resolva um radical exato ou uma aproximação restrita.

        Args:
            palavra (str): Radical consultado.

        Returns:
            str: Chave procurada nas postagens do índice.
        """
        return palavra if palavra in self._postagens else aproximar(palavra, self._vocabulario)

    def _peso(self, palavra):
        """Dê mais peso a termos específicos e não ignore palavras desconhecidas.

        Args:
            palavra (str): Radical da consulta.

        Returns:
            float: Peso IDF usado na cobertura, não probabilidade factual.
        """
        frequencia = len(self._postagens.get(palavra, ()))
        return log(1 + (len(self._textos) + 0.5) / (frequencia + 0.5))

    def _pontuar(self, posicao, pesos):
        """Calcule a cobertura de uma evidência sem mudar seu texto.

        Args:
            posicao (int): Posição do trecho no snapshot.
            pesos (dict): Pesos dos termos da consulta.

        Returns:
            TrechoDocumento: Cópia com pontuação de recuperação.
        """
        coberto = sum(peso for p, peso in pesos.items() if posicao in self._postagens.get(p, ()))
        return replace(self._textos[posicao], similaridade=coberto / max(1e-9, sum(pesos.values())))

    def _permitido(self, posicao, cursos):
        """Restrinja documentos do outro curso sem excluir publicações gerais.

        Args:
            posicao (int): Posição da evidência.
            cursos (set): Cursos mencionados na pergunta.

        Returns:
            bool: Indica se a evidência atende ao filtro.
        """
        return not cursos or not self._textos[posicao].curso or self._textos[posicao].curso in cursos
