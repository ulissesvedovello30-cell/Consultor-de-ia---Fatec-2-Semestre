"""Adaptador ASGI dos controles de entrada e tráfego; sem regras de negócio."""
import hashlib
import hmac
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from seguranca.corpo import LeitorLimitado, Repetidor, ler_json
from seguranca.entrada import preparar, validar_json


class GatewaySeguranca:
    """Aplique controles a todas as rotas, inclusive requisições recusadas."""

    def __init__(self, app, trafego, sal):
        """Injete próximo aplicativo, limitador e segredo efêmero de pseudonimização."""
        self.app, self.trafego, self.sal = app, trafego, sal

    async def __call__(self, scope, receive, send):
        """Atenda HTTP sob limites; preserve eventos de ciclo de vida ASGI."""
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        try:
            self.trafego.entrar(self._chave(scope))
        except HTTPException as erro:
            return await recusar(erro, scope, receive, send)
        try:
            return await self._atender(scope, receive, send)
        finally:
            self.trafego.sair()

    def _chave(self, scope):
        """Use o peer ASGI, nunca um X-Forwarded-For fornecido diretamente pelo cliente."""
        ip = (scope.get('client') or ('local',))[0]
        return hmac.new(self.sal, ip.encode(), hashlib.sha256).hexdigest()

    async def _atender(self, scope, receive, send):
        """Prepare o corpo validado antes de entregar a requisição ao framework."""
        try:
            receptor = await preparar_receptor(scope, receive)
        except HTTPException as erro:
            return await recusar(erro, scope, receive, send)
        except (ValueError, UnicodeError):
            return await recusar(HTTPException(400, 'Requisição inválida.'), scope, receive, send)
        await self.app(scope, receptor, send)


async def preparar_receptor(scope, receive):
    """Retorne receive limitado; para JSON, valide o corpo antes do Pydantic."""
    limite, tipo_json, segundos = preparar(scope)
    leitor = LeitorLimitado(receive, limite, segundos)
    if not tipo_json:
        return leitor.receber
    bruto = await ler_json(leitor)
    validar_json(bruto)
    return Repetidor(bruto, receive).receber


async def recusar(erro, scope, receive, send):
    """Retorne erro HTTP sanitizado, sem reproduzir qualquer payload recebido."""
    resposta = JSONResponse({'detail': erro.detail}, status_code=erro.status_code, headers=erro.headers)
    await resposta(scope, receive, send)
