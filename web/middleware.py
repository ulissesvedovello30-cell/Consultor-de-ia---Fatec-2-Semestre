"""Cabeçalhos de resposta e sanitização de erros imprevistos."""
async def cabecalhos(request, call_next):
    """Acrescente controles de cache, conteúdo, enquadramento e origem às respostas."""
    resposta = await atender_com_erro(request, call_next)
    resposta.headers['Cache-Control'] = 'no-store'
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    resposta.headers['X-Frame-Options'] = 'DENY'
    resposta.headers['Referrer-Policy'] = 'no-referrer'
    resposta.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    proteger_transporte(request, resposta)
    return resposta


async def atender_com_erro(request, call_next):
    """Capture falhas inesperadas sem propagar conteúdo privado para logs do servidor."""
    from web.aplicacao import erro_inesperado
    try:
        return await call_next(request)
    except Exception as erro:
        return await erro_inesperado(request, erro)


def proteger_transporte(request, resposta):
    """Aplique HSTS apenas à origem configurada com HTTPS, sem confiar no cliente."""
    resposta.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.app.state.config.seguro:
        resposta.headers['Strict-Transport-Security'] = 'max-age=31536000'
