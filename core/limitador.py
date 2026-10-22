import time
from collections import deque


class LimitadorTaxa:
    """Janela deslizante: no máximo `limite` ações por chave a cada `janela` segundos (em memória)."""

    _LIMITE_DE_CHAVES = 5000  # acima disso, descarta as chaves que já esfriaram

    def __init__(self, limite: int, janela: float, relogio=time.monotonic):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        if limite <= 0 or janela <= 0:
            raise ValueError("limite e janela devem ser maiores que zero.")
        self._limite = limite
        self._janela = janela
        self._relogio = relogio
        self._eventos: dict[str, deque[float]] = {}

    def permitir(self, chave: str) -> bool:
        """Registre uma ação permitida ou retorne falso ao exceder janela ou capacidade."""
        agora = self._relogio()
        self._descartar_antigas(agora)

        if chave not in self._eventos and len(self._eventos) >= self._LIMITE_DE_CHAVES:
            return False
        eventos = self._eventos.setdefault(chave, deque())
        self._expirar_eventos(eventos, agora)
        if len(eventos) >= self._limite:
            return False
        eventos.append(agora)
        return True

    def _descartar_antigas(self, agora: float) -> None:
        """Remova chaves sem eventos dentro da janela temporal vigente."""
        self._eventos = {c: e for c, e in self._eventos.items() if e and e[-1] > agora - self._janela}

    def _expirar_eventos(self, eventos, agora):
        """Descarte timestamps fora da janela de uma chave."""
        while eventos and eventos[0] <= agora - self._janela:
            eventos.popleft()

    def expirar(self):
        """Remova chaves vencidas na limpeza periódica, mesmo sem novas requisições."""
        self._descartar_antigas(self._relogio())
