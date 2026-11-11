"""Leitura ASGI limitada por bytes e tempo total, sem depender de Content-Length."""
import asyncio
import time
from starlette.exceptions import HTTPException


class LeitorLimitado:
    """Envolva receive com limites reais de corpo e prazo acumulado."""

    def __init__(self, receber, limite, segundos):
        """Receba callable ASGI, máximo de bytes e prazo total de leitura."""
        self.original, self.limite = receber, limite
        self.total, self.fim = 0, time.monotonic() + segundos

    async def receber(self):
        """Retorne um bloco ASGI ou lance 408/413 sem continuar a leitura."""
        try:
            mensagem = await asyncio.wait_for(self.original(), max(0, self.fim - time.monotonic()))
        except TimeoutError:
            raise HTTPException(408, 'Tempo de envio excedido.') from None
        self.total += len(mensagem.get('body', b''))
        if self.total > self.limite:
            raise HTTPException(413, 'Requisição muito grande.')
        return mensagem


async def ler_json(leitor):
    """Acumule um corpo pequeno e completo, recusando desconexão prematura."""
    blocos = []
    while True:
        mensagem = await leitor.receber()
        if mensagem['type'] != 'http.request':
            raise HTTPException(400, 'Envio interrompido.')
        blocos.append(mensagem.get('body', b''))
        if not mensagem.get('more_body', False):
            return b''.join(blocos)


class Repetidor:
    """Reapresente ao framework o corpo já validado, uma única vez."""

    def __init__(self, bruto, original):
        """Guarde corpo limitado e canal original para detectar desconexão posterior."""
        self.bruto, self.original = bruto, original

    async def receber(self):
        """Entregue o corpo validado ou aguarde o canal ASGI original."""
        if self.bruto is None:
            return await self.original()
        bruto, self.bruto = self.bruto, None
        return {'type': 'http.request', 'body': bruto, 'more_body': False}
