import numpy as np

from dominio.trecho_documento import TrechoDocumento


class RepositorioEmMemoria:
    """Mesma interface do RepositorioTrechos, sem banco: para testes e para a demonstração offline.

    Tudo se perde ao fechar o programa.
    """

    def __init__(self):
        # hash do arquivo -> (modelo, trechos, vetores)
        self._arquivos: dict[str, tuple[str, list[TrechoDocumento], np.ndarray]] = {}

    def indexado(self, hash_arquivo: str, modelo_embedding: str) -> bool:
        guardado = self._arquivos.get(hash_arquivo)
        return guardado is not None and guardado[0] == modelo_embedding

    def substituir_arquivo(
        self,
        hash_arquivo: str,
        modelo_embedding: str,
        trechos: list[TrechoDocumento],
        embeddings: np.ndarray,
    ) -> None:
        if len(trechos) != len(embeddings):
            raise ValueError("Cada trecho precisa de exatamente um vetor.")
        self._arquivos[hash_arquivo] = (modelo_embedding, list(trechos), np.asarray(embeddings, dtype=np.float32))

    def carregar(self, modelo_embedding: str) -> tuple[list[TrechoDocumento], np.ndarray]:
        do_modelo = [(t, v) for m, t, v in self._arquivos.values() if m == modelo_embedding]
        if not do_modelo:
            return [], np.empty((0, 0), dtype=np.float32)
        trechos = [t for ts, _ in do_modelo for t in ts]
        return trechos, np.vstack([v for _, v in do_modelo])
