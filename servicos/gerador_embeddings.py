import threading

import numpy as np


class GeradorEmbeddings:
    """Transforma textos em vetores (modelo do Hugging Face, roda na máquina)."""

    def __init__(self, nome_modelo: str):
        self.nome_modelo = nome_modelo
        self._modelo = None
        # Protege o carregamento (evita carregar duas vezes) e o uso do modelo.
        self._trava = threading.Lock()

    def carregar(self) -> None:
        """Carrega o modelo agora. Chame na inicialização para falhar cedo, não na 1ª pergunta."""
        with self._trava:
            self._garantir_modelo()

    def codificar(self, textos: list[str]) -> np.ndarray:
        """Vetores float32 normalizados (norma 1): o produto escalar vira a similaridade de cosseno."""
        with self._trava:
            modelo = self._garantir_modelo()
            vetores = modelo.encode(
                textos,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False,
            )
        return vetores.astype(np.float32)

    def contar_acima_do_limite(self, textos: list[str]) -> int:
        """Quantos textos passam do limite de tokens do modelo (o excesso é cortado antes de virar vetor)."""
        with self._trava:
            modelo = self._garantir_modelo()
            limite = getattr(modelo, "max_seq_length", None)
            if not limite:
                return 0
            try:
                ids = modelo.tokenizer(textos, add_special_tokens=True, truncation=False)["input_ids"]
            except Exception:
                return 0  # diagnóstico opcional: não pode impedir a indexação
        return sum(1 for i in ids if len(i) > limite)

    def _garantir_modelo(self):
        if self._modelo is None:
            # import tardio: carregar torch leva segundos e só quem usa o modelo paga isso
            from sentence_transformers import SentenceTransformer

            self._modelo = SentenceTransformer(self.nome_modelo)
        return self._modelo
