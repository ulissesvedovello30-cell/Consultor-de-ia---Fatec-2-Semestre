"""Orçamento temporal compartilhado pelas chamadas HTTP de uma operação."""
import time
from contextvars import ContextVar

FIM = ContextVar('prazo_operacao', default=None)


def restante():
    """Retorne segundos disponíveis; lance TimeoutError se o prazo expirou."""
    fim = FIM.get()
    segundos = 30.0 if fim is None else min(30.0, fim - time.monotonic())
    if segundos <= 0:
        raise TimeoutError('Prazo da operação excedido.')
    return segundos


def executar(funcao, args, fim):
    """Execute funcao(*args, prazo_final=fim) com orçamento temporal isolado."""
    token = FIM.set(fim)
    try:
        return funcao(*args, prazo_final=fim)
    finally:
        FIM.reset(token)
