"""Peças falsas para testar o fluxo inteiro sem baixar modelos nem chamar o Gemini.

Não servem para atendimento de verdade: o embedding só compara palavras (não entende
sinônimos como embeddings semânticos) e o gerador apenas devolve os trechos encontrados.
"""
import hashlib
import json
import re
import unicodedata

import numpy as np


class EmbeddingsLexicais:
    """Vetor de palavras (contagem em 1024 posições), sem rede neural."""

    nome_modelo = "demo-lexical-v1"
    _DIMENSAO = 1024
    _IGNORAR = set(
        "a o as os de da do das dos e em no na nos nas um uma que qual quais quando onde como para por "
        "com meu minha eu quero saber sobre turma semestre fatec dia horario".split()
    )

    def codificar(self, textos: list[str]) -> np.ndarray:
        """Retorne matriz de vetores lexicais normalizados, sem acesso à rede."""
        return np.vstack([self._vetor(t) for t in textos]).astype(np.float32)

    def _vetor(self, texto: str) -> np.ndarray:
        """Retorne um vetor normalizado de contagens de palavras para demonstração."""
        sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if not unicodedata.combining(c))
        vetor = np.zeros(self._DIMENSAO, dtype=np.float32)
        for palavra in re.findall(r"[a-z0-9]+", sem_acento):
            if palavra in self._IGNORAR:
                continue
            posicao = int.from_bytes(hashlib.blake2b(palavra.encode(), digest_size=8).digest(), "big") % self._DIMENSAO
            vetor[posicao] += 1
        norma = np.linalg.norm(vetor)
        return vetor / norma if norma else vetor


class GeradorExtrativo:
    """Devolve os dois primeiros trechos do contexto, no mesmo formato JSON que o modelo de verdade deveria usar."""

    def gerar(self, mensagens: list[dict[str, str]]) -> str:
        """Selecione os dois primeiros trechos e retorne JSON extrativo de demonstração."""
        contexto = mensagens[-1]["content"].split("\n\nPERGUNTA:", 1)[0]
        trechos = re.findall(r"\[Trecho (\d+) \|[^\]\n]*\]\n(.*?)(?=\n\n---\n\n|\Z)", contexto, re.S)
        afirmacoes = [{"texto": re.sub(r"^[-•–*]\s+", "", t.strip()), "fontes": [int(i)]} for i, t in trechos[:2]]
        status = "respondida" if afirmacoes else "insuficiente"
        return json.dumps({"status": status, "afirmacoes": afirmacoes}, ensure_ascii=False)
