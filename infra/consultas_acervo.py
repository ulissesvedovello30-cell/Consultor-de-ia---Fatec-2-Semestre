from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from sqlalchemy import select, or_
from dominio.trecho_documento import TrechoDocumento
from infra.esquema import documentos as d, versoes as v, trechos as t


def juntar_ativos():
    """Retorne a junção SQL entre documentos e suas versões ativas."""
    return d.join(v, d.c.versao_ativa == v.c.id)


def consulta_trechos(modelo):
    """Monte a consulta SQL de trechos ativos de um modelo de embedding."""
    colunas = [d.c.nome, d.c.id.label('documento_id'), v, t.c.pagina, t.c.texto, t.c.embedding]
    consulta = select(*colunas).select_from(juntar_ativos().join(t, t.c.versao_id == v.c.id))
    return consulta.where(v.c.modelo_embedding == modelo).order_by(t.c.id)


def consulta_vigente(modelo):
    """Restrinja a consulta ao intervalo de vigência na data de São Paulo."""
    hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    return consulta_trechos(modelo).where(
        or_(v.c.inicio.is_(None), v.c.inicio <= hoje),
        or_(v.c.fim.is_(None), v.c.fim >= hoje),
    )


def converter_trecho(linha):
    """Converta uma linha SQL em trecho documental com metadados e identificadores."""
    campos = ('curso', 'periodo', 'ano', 'inicio', 'fim', 'url_oficial')
    return TrechoDocumento(
        linha['nome'], linha['pagina'], linha['texto'],
        documento_id=linha['documento_id'], versao_id=linha['id'],
        **{campo: linha[campo] for campo in campos},
    )


def converter_indice(linhas):
    """Converta linhas SQL em trechos e matriz; rejeite vetores não finitos."""
    if not linhas:
        return [], np.empty((0, 0), dtype=np.float32)
    matriz = np.vstack([np.frombuffer(l['embedding'], dtype='<f4') for l in linhas])
    if not np.isfinite(matriz).all():
        raise ValueError('Índice contém vetores inválidos; reindexe o acervo.')
    return [converter_trecho(l) for l in linhas], matriz.astype(np.float32)
