import secrets
import time
from dataclasses import dataclass, field
from fastapi import HTTPException


@dataclass
class Sessao:
    fim: float
    csrf: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    conversa: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    admin: bool = False
    admin_fim: float = 0
    ocupada: bool = False


class Sessoes:
    def __init__(self, ttl=3600, relogio=time.monotonic):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self._itens, self.ttl, self.relogio = {}, ttl, relogio

    def obter(self, token):
        """Retorne sessão válida e descarte as sessões cujo prazo terminou."""
        agora = self.relogio()
        self._itens = {k: v for k, v in self._itens.items() if v.fim > agora}
        return self._itens.get(token)

    def criar(self):
        """Crie sessão opaca limitada em quantidade; retorne token e estado da sessão."""
        self.obter(None)
        if len(self._itens) >= 5000:
            raise HTTPException(503, 'Sessões ocupadas. Tente mais tarde.')
        token = secrets.token_urlsafe(32)
        sessao = Sessao(self.relogio() + self.ttl)
        self._itens[token] = sessao
        return token, sessao

    def revogar(self, token):
        """Remova imediatamente a sessão associada ao token, se existir."""
        self._itens.pop(token, None)
