import time
from collections import deque


class LimitadorTaxa:
    """Janela deslizante: no máximo `limite` ações por chave a cada `janela` segundos (em memória)."""

    _LIMITE_DE_CHAVES = 5000  # acima disso, descarta as chaves que já esfriaram

    def __init__(self, limite: int, janela: float, relogio=time.monotonic):
        if limite <= 0 or janela <= 0:
            raise ValueError("limite e janela devem ser maiores que zero.")
        self._limite = limite
        self._janela = janela
        self._relogio = relogio
        self._eventos: dict[str, deque[float]] = {}

    def permitir(self, chave: str) -> bool:
        agora = self._relogio()
        if len(self._eventos) > self._LIMITE_DE_CHAVES:
            self._descartar_antigas(agora)

        eventos = self._eventos.setdefault(chave, deque())
        while eventos and eventos[0] <= agora - self._janela:
            eventos.popleft()
        if len(eventos) >= self._limite:
            return False
        eventos.append(agora)
        return True

    def _descartar_antigas(self, agora: float) -> None:
        self._eventos = {c: e for c, e in self._eventos.items() if e and e[-1] > agora - self._janela}
