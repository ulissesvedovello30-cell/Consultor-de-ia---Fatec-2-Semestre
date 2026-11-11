"""Progresso privado ao carregamento inicial; lotes parciais não ficam consultáveis."""
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
import numpy as np
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from infra.esquema import lotes_iniciais as lotes

_ENGINE = ContextVar('engine_lotes_iniciais', default=None)


@contextmanager
def memorizar_lotes(engine):
    """Ative o reaproveitamento apenas durante a publicação dos documentos iniciais."""
    token = _ENGINE.set(engine)
    try:
        yield
    finally:
        _ENGINE.reset(token)


def chave_lote(modelo, textos):
    """Identifique o modelo e a sequência exata de textos sem gravar os textos."""
    dados = json.dumps([modelo, textos], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(dados.encode()).hexdigest()


def ler(engine, chave, linhas):
    """Carregue uma matriz compatível; ignore um registro incompleto ou inválido."""
    with engine.connect() as conexao:
        bruto = conexao.scalar(select(lotes.c.vetores).where(lotes.c.hash == chave))
    if bruto is None or len(bruto) != linhas * 768 * 4:
        return None
    matriz = np.frombuffer(bruto, dtype='<f4').reshape(linhas, 768)
    if np.isfinite(matriz).all() and np.allclose(np.linalg.norm(matriz, axis=1), 1, atol=1e-5):
        return matriz
    return None


def salvar(engine, chave, matriz):
    """Grave um lote concluído antes de pedir o próximo ao provedor."""
    dados = np.asarray(matriz, dtype='<f4').tobytes()
    with engine.begin() as conexao:
        conexao.execute(insert(lotes).values(hash=chave, vetores=dados)
                        .on_conflict_do_update(index_elements=[lotes.c.hash], set_={'vetores': dados}))


def obter_lote(gerar, modelo, textos):
    """Reutilize lotes bem-sucedidos da carga inicial ou solicite um novo."""
    engine = _ENGINE.get()
    if engine is None:
        return gerar(textos)
    chave = chave_lote(modelo, textos)
    matriz = ler(engine, chave, len(textos))
    if matriz is None:
        matriz = gerar(textos)
        salvar(engine, chave, matriz)
    return matriz
