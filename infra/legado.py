"""Importa apenas documentos legados sem versões conflitantes; nunca apaga o original."""
from collections import defaultdict
import numpy as np
from sqlalchemy import MetaData, Table, select
from dominio.erros import ErroIndexacao
from dominio.trecho_documento import TrechoDocumento
from infra.repositorio_trechos import RepositorioTrechos


def agrupar(linhas):
    """Agrupe linhas legadas por arquivo; recuse hashes conflitantes."""
    grupos = defaultdict(list)
    for linha in linhas:
        grupos[linha.arquivo].append(linha)
    conflitos = [nome for nome, itens in grupos.items() if len({i.hash_arquivo for i in itens}) > 1]
    if conflitos:
        raise ErroIndexacao('Há versões legadas conflitantes. Reindexe os originais atuais: ' + ', '.join(conflitos))
    return grupos


def importar_documento(repo, nome, linhas, modelo):
    """Importe um grupo documental legado sem misturar arquivos de versões conflitantes."""
    if repo.indexado(linhas[0].hash_arquivo, modelo, nome):
        return 0
    if any(doc['nome'].casefold() == nome.casefold() for doc in repo.listar()):
        raise ErroIndexacao(f'{nome} já possui versão ativa diferente. Migração não a sobrescreverá.')
    trechos = [TrechoDocumento(nome, linha.pagina, linha.texto) for linha in linhas]
    vetores = np.vstack([np.frombuffer(linha.embedding, dtype='<f4') for linha in linhas])
    repo.substituir_arquivo(linhas[0].hash_arquivo, modelo, trechos, vetores)
    return len(trechos)


def migrar(engine, modelo):
    """Migre registros legados válidos para o esquema de documentos versionados."""
    tabela = Table('trecho_documento', MetaData(), autoload_with=engine)
    with engine.connect() as conexao:
        linhas = conexao.execute(select(tabela).where(tabela.c.modelo_embedding == modelo)).all()
    grupos = agrupar(linhas)  # conferir todos os conflitos antes de escrever
    repo = RepositorioTrechos(engine)
    return sum(importar_documento(repo, nome, itens, modelo) for nome, itens in grupos.items())
