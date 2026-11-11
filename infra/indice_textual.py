"""Índice FTS5 sincronizado com os trechos; não utiliza modelos nem APIs."""
from sqlalchemy import text, table, column, select, update
from sqlalchemy.exc import SQLAlchemyError
from dominio.erros import ErroBancoDeDados
from infra.consultas_acervo import consulta_vigente, converter_trecho
from infra.esquema import trechos, documentos, versoes


def criar_indice(engine):
    """Prepare FTS5 e gatilhos de sincronização sem alterar os textos originais.

    Args:
        engine: Conexão SQLite do acervo.

    Raises:
        ErroBancoDeDados: Se o SQLite instalado não oferecer FTS5.
    """
    try:
        with engine.begin() as c:
            existente = c.scalar(text("SELECT name FROM sqlite_master WHERE name='rag_busca_textual'"))
            c.exec_driver_sql("CREATE VIRTUAL TABLE IF NOT EXISTS rag_busca_textual USING fts5(texto, content='rag_trecho', content_rowid='id', tokenize='unicode61 remove_diacritics 2')")
            criar_gatilhos(c)
            if existente is None:
                c.exec_driver_sql("INSERT INTO rag_busca_textual(rag_busca_textual) VALUES ('rebuild')")
    except SQLAlchemyError as erro:
        raise ErroBancoDeDados('Não foi possível preparar FTS5. Use um Python com SQLite FTS5 habilitado.') from erro


def criar_gatilhos(c):
    """Mantenha inclusões, exclusões e substituições dentro da transação do documento."""
    c.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS rag_busca_ai AFTER INSERT ON rag_trecho BEGIN
        INSERT INTO rag_busca_textual(rowid,texto) VALUES (new.id,new.texto); END""")
    c.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS rag_busca_ad AFTER DELETE ON rag_trecho BEGIN
        INSERT INTO rag_busca_textual(rag_busca_textual,rowid,texto) VALUES ('delete',old.id,old.texto); END""")
    c.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS rag_busca_au AFTER UPDATE ON rag_trecho BEGIN
        INSERT INTO rag_busca_textual(rag_busca_textual,rowid,texto) VALUES ('delete',old.id,old.texto);
        INSERT INTO rag_busca_textual(rowid,texto) VALUES (new.id,new.texto); END""")


def buscar(repo, modelo, expressao, k, cursos=()):
    """Ordene trechos vigentes por BM25 usando expressão previamente escapada.

    Args:
        repo: Repositório transacional compartilhado.
        modelo (str): Identidade do acervo.
        expressao (str): Termos protegidos da sintaxe FTS.
        k (int): Quantidade máxima de candidatos.

    Returns:
        list: Trechos ativos, com seus metadados e páginas.
    """
    indice = table('rag_busca_textual', column('rowid'))
    consulta = consulta_vigente(modelo).join(indice, indice.c.rowid == trechos.c.id)
    consulta = consulta.where(text('rag_busca_textual MATCH :termos')).params(termos=expressao)
    if cursos:
        consulta = consulta.where(versoes.c.curso.in_(cursos) | (versoes.c.curso == ''))
    consulta = consulta.order_by(None).order_by(text('bm25(rag_busca_textual)'), trechos.c.id)
    return [converter_trecho(linha) for linha in repo._ler(consulta.limit(k))]


def migrar_publicados(engine, modelo):
    """Torne documentos ativos legados pesquisáveis sem chamar embeddings.

    Args:
        engine: Conexão SQLite preparada.
        modelo (str): Identidade do novo método de recuperação.
    """
    ativos = select(documentos.c.versao_ativa).where(documentos.c.versao_ativa.is_not(None))
    with engine.begin() as c:
        c.execute(update(versoes).where(versoes.c.id.in_(ativos),
            versoes.c.modelo_embedding != modelo).values(modelo_embedding=modelo))
