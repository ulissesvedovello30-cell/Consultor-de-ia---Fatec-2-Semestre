"""Prazo total e ocupação preservada até a thread realmente terminar."""
import asyncio
import threading
import time
from servicos.prazo import executar
from dominio.erros import ErroOcupado, ErroPrazo


class ExecutorRAG:
    def __init__(self, prazo=120, capacidade=2):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self.prazo = prazo
        self._vagas = threading.BoundedSemaphore(capacidade)
        self._serial = threading.Lock()

    async def executar(self, funcao, *args):
        """Execute trabalho bloqueante com capacidade e prazo total limitados."""
        if not self._vagas.acquire(blocking=False):
            raise ErroOcupado('Consultor ocupado.')
        tarefa = asyncio.create_task(asyncio.to_thread(self._trabalhar, funcao, args, time.monotonic() + self.prazo))
        tarefa.add_done_callback(consumir_excecao)
        try:
            return await asyncio.wait_for(asyncio.shield(tarefa), self.prazo)
        except TimeoutError as erro:
            raise ErroPrazo('Tempo total de atendimento excedido.') from erro

    def _trabalhar(self, funcao, args, fim):
        """Execute uma operação e libere sua vaga somente quando a thread terminar."""
        try:
            return self._serializar(funcao, args, fim)
        finally:
            self._vagas.release()

    def _serializar(self, funcao, args, fim):
        """Adquira a trava dentro do prazo e execute a função com orçamento temporal."""
        if not self._serial.acquire(timeout=max(0, fim - time.monotonic())):
            raise ErroPrazo('Tempo de espera excedido.')
        try:
            if time.monotonic() >= fim:
                raise ErroPrazo('Tempo de espera excedido.')
            return executar(funcao, args, fim)
        finally:
            self._serial.release()


def consumir_excecao(tarefa):
    """Consuma a exceção da tarefa concluída para evitar logs de dados internos."""
    if not tarefa.cancelled():
        tarefa.exception()
