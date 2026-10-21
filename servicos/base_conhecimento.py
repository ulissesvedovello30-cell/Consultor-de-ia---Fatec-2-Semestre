import hashlib
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np

from dominio.erros import ErroIndexacao
from dominio.trecho_documento import TrechoDocumento
from servicos.processador_documento import dividir_em_trechos, extrair_paginas

logger = logging.getLogger(__name__)


class BaseConhecimento:
    """Indexa documentos (.pdf, .docx, .txt) e busca os trechos mais parecidos com uma pergunta.

    `repositorio` guarda trechos e vetores (MySQL, ou memória nos testes/demonstração).
    `embedder` é qualquer objeto com `codificar(list[str]) -> np.ndarray` de vetores
    normalizados e um atributo `nome_modelo`.
    """

    def __init__(self, repositorio, embedder, modelo_embedding: str | None = None):
        self._repositorio = repositorio
        self._embedder = embedder
        self._modelo_embedding = modelo_embedding or embedder.nome_modelo
        # Trechos e matriz são trocados numa única atribuição: uma busca em andamento
        # nunca enxerga trechos de uma versão com vetores de outra.
        self._indice: tuple[list[TrechoDocumento], np.ndarray] = ([], np.empty((0, 0), dtype=np.float32))

    @property
    def total_trechos(self) -> int:
        return len(self._indice[0])

    def carregar(self) -> None:
        """Lê do repositório tudo o que já foi indexado. Chame na inicialização e depois de indexar."""
        self._indice = self._repositorio.carregar(self._modelo_embedding)
        logger.info("Base de conhecimento carregada: %d trechos", self.total_trechos)

    def indexar_arquivo(self, caminho: Path, forcar: bool = False, tamanho_trecho: int = 450) -> int:
        """Indexa um documento e devolve quantos trechos gravou (0 se já estava indexado).

        `tamanho_trecho` é o máximo de caracteres por trecho. O padrão (450) cabe nos 128
        tokens do modelo de embeddings; valores maiores só valem para outro modelo.
        Mudar o tamanho de um arquivo já indexado exige `forcar=True`.
        """
        try:
            hash_arquivo = hashlib.sha256(caminho.read_bytes()).hexdigest()
        except OSError as e:
            raise ErroIndexacao(f"Não foi possível abrir '{caminho.name}'") from e

        if not forcar and self._repositorio.indexado(hash_arquivo, self._modelo_embedding):
            logger.info("'%s' já está indexado; nada a fazer", caminho.name)
            return 0

        trechos = [
            TrechoDocumento(arquivo=caminho.name, pagina=pagina, texto=texto)
            for pagina, texto_pagina in extrair_paginas(caminho)
            for texto in dividir_em_trechos(texto_pagina, tamanho_trecho, sobreposicao=tamanho_trecho // 6)
        ]
        textos = [t.texto for t in trechos]

        contar = getattr(self._embedder, "contar_acima_do_limite", None)
        if contar is not None and (cortados := contar(textos)):
            logger.warning(
                "%d de %d trechos passam do limite de tokens do modelo de embeddings e serão "
                "cortados antes de virar vetor. Use um tamanho de trecho menor.",
                cortados,
                len(textos),
            )

        embeddings = self._embedder.codificar(textos)
        self._repositorio.substituir_arquivo(hash_arquivo, self._modelo_embedding, trechos, embeddings)
        self.carregar()
        return len(trechos)

    def buscar(self, pergunta: str, k: int = 5) -> list[TrechoDocumento]:
        """Os `k` trechos mais parecidos com a pergunta, do mais para o menos parecido."""
        trechos, matriz = self._indice  # cópia local: ver comentário do __init__
        if not trechos:
            return []

        vetor = self._embedder.codificar([pergunta])[0]
        similaridades = matriz @ vetor  # vetores normalizados: produto escalar = cosseno

        k = min(max(1, k), len(trechos))
        candidatos = np.argpartition(-similaridades, k - 1)[:k]
        melhores = candidatos[np.argsort(-similaridades[candidatos])]
        return [replace(trechos[i], similaridade=float(similaridades[i])) for i in melhores]
