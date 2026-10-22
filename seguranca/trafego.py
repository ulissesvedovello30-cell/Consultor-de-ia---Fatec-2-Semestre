"""Controle de carga de aplicação, independente das operações administrativas."""
import threading
from core.limitador import LimitadorTaxa
from starlette.exceptions import HTTPException


class ControleTrafego:
    """Limite volume e simultaneidade antes de ler payloads ou chamar serviços."""

    def __init__(self):
        """Configure cotas finitas para um processo de atendimento."""
        self.global_ = LimitadorTaxa(600, 60)
        self.por_ip = LimitadorTaxa(120, 60)
        self.vagas = threading.BoundedSemaphore(24)

    def entrar(self, chave):
        """Reserve capacidade sem criar fila; lance 429 ou 503 quando ocupada."""
        if not self.global_.permitir('http') or not self.por_ip.permitir(chave):
            raise HTTPException(429, 'Limite de requisições.', headers={'Retry-After': '60'})
        if not self.vagas.acquire(blocking=False):
            raise HTTPException(503, 'Servidor ocupado.', headers={'Retry-After': '5'})

    def sair(self):
        """Libere a vaga somente quando o atendimento HTTP realmente terminar."""
        self.vagas.release()

    def expirar(self):
        """Descarte identificadores temporários sem atividade recente."""
        self.global_.expirar()
        self.por_ip.expirar()
