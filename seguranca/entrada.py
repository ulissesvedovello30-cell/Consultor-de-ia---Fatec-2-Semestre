"""Validação estrutural de mensagens HTTP; não presume que o cliente seja confiável."""
import json
from urllib.parse import parse_qsl
from starlette.exceptions import HTTPException

CABECALHOS_UNICOS = {b'host', b'content-length', b'content-type', b'origin', b'cookie', b'x-csrf-token', b'transfer-encoding', b'content-encoding'}
CAMPOS_UPLOAD = {'nome', 'curso', 'periodo', 'ano', 'inicio', 'fim', 'url_oficial', 'publico'}
ROTAS_JSON = {'/api/chat', '/api/admin/login'}


def cabecalhos(scope):
    """Recuse cabeçalhos críticos duplicados, tamanho excessivo e enquadramento ambíguo."""
    itens = scope.get('headers', [])
    if len(itens) > 64 or sum(len(k) + len(v) for k, v in itens) > 16384:
        raise HTTPException(431, 'Cabeçalhos excedem o limite.')
    nomes = [k.lower() for k, _ in itens]
    if any(nomes.count(k) > 1 for k in CABECALHOS_UNICOS):
        raise HTTPException(400, 'Cabeçalhos ambíguos.')
    mapa = {k.lower(): v for k, v in itens}
    validar_enquadramento(mapa)
    return mapa


def validar_enquadramento(mapa):
    """Recuse CL+TE, compressão não suportada e Content-Length não decimal."""
    if b'content-length' in mapa and b'transfer-encoding' in mapa:
        raise HTTPException(400, 'Enquadramento ambíguo.')
    tamanho = mapa.get(b'content-length', b'0')
    if not tamanho.isdigit() or len(tamanho) > 10:
        raise HTTPException(400, 'Content-Length inválido.')
    if mapa.get(b'transfer-encoding', b'chunked').lower() != b'chunked':
        raise HTTPException(400, 'Transfer-Encoding não suportado.')
    if mapa.get(b'content-encoding', b'identity').lower() != b'identity':
        raise HTTPException(415, 'Corpo comprimido não suportado.')


def validar_query(scope):
    """Recuse parâmetros desconhecidos ou repetidos e limite o tamanho da URL."""
    query = scope.get('query_string', b'')
    if len(query) > 4096 or len(scope.get('raw_path', b'')) > 2048:
        raise HTTPException(414, 'URL excede o limite.')
    pares = parse_qsl(query.decode('utf-8', errors='strict'), keep_blank_values=True, max_num_fields=16)
    permitidos = CAMPOS_UPLOAD if scope['path'] == '/api/admin/documentos' and scope['method'] == 'POST' else set()
    nomes = [k for k, _ in pares]
    if len(set(nomes)) != len(nomes) or set(nomes) - permitidos:
        raise HTTPException(422, 'Parâmetros desconhecidos ou repetidos.')


def validar_json(bruto):
    """Decodifique um objeto JSON limitado, sem chaves duplicadas ou números não finitos."""
    try:
        objeto = json.loads(bruto.decode('utf-8'), object_pairs_hook=pares_unicos, parse_constant=constante_invalida)
        if not isinstance(objeto, dict):
            raise ValueError('Objeto esperado.')
        conferir_profundidade(objeto)
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(400, 'JSON inválido ou ambíguo.') from None


def pares_unicos(pares):
    """Construa objeto rejeitando a interpretação ambígua de chaves repetidas."""
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError('Chave repetida.')
        objeto[chave] = valor
    return objeto


def constante_invalida(valor):
    """Recuse NaN e Infinity, que não pertencem ao contrato JSON da aplicação."""
    raise ValueError('Constante não permitida.')


def conferir_profundidade(objeto, nivel=0):
    """Recuse estruturas aninhadas além de quatro níveis e coleções extensas."""
    if nivel > 4:
        raise ValueError('JSON muito aninhado.')
    itens = objeto.values() if isinstance(objeto, dict) else objeto if isinstance(objeto, list) else ()
    if len(itens) > 16:
        raise ValueError('Coleção muito extensa.')
    for item in itens:
        conferir_profundidade(item, nivel + 1)


def preparar(scope):
    """Valide metadados HTTP antes de ler o corpo; retorne limites e modo JSON."""
    mapa = cabecalhos(scope)
    validar_query(scope)
    upload = scope['path'] == '/api/admin/documentos' and scope['method'] == 'POST'
    limite = 25 * 1024 * 1024 if upload else 8192
    if int(mapa.get(b'content-length', b'0')) > limite:
        raise HTTPException(413, 'Requisição muito grande.')
    tipo_json = scope['method'] == 'POST' and scope['path'] in ROTAS_JSON
    validar_tipo(scope, mapa, tipo_json)
    return limite, tipo_json, 60 if upload else 5


def validar_tipo(scope, mapa, tipo_json):
    """Exija JSON nas rotas estruturadas e recuse corpos em GET, HEAD e DELETE."""
    tipo = mapa.get(b'content-type', b'').lower().replace(b' ', b'')
    if tipo_json and tipo not in {b'application/json', b'application/json;charset=utf-8'}:
        raise HTTPException(415, 'Envie application/json em UTF-8.')
    if scope['method'] in {'GET', 'HEAD', 'DELETE'} and (int(mapa.get(b'content-length', b'0')) or b'transfer-encoding' in mapa):
        raise HTTPException(400, 'Este método não aceita corpo.')
