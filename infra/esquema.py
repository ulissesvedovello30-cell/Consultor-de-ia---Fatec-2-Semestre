"""Tabelas exclusivas do consultor; não acessam cadastro de alunos."""
from sqlalchemy import (MetaData, Table, Column, String, Text, Integer,
                        LargeBinary, Date, ForeignKey)

metadata = MetaData()
documentos = Table(
    'rag_documento', metadata,
    Column('id', String(64), primary_key=True),
    Column('nome', String(255), nullable=False),
    Column('versao_ativa', String(32)),
)
versoes = Table(
    'rag_versao', metadata,
    Column('id', String(32), primary_key=True),
    Column('documento_id', ForeignKey('rag_documento.id'), nullable=False, index=True),
    Column('hash_arquivo', String(64), nullable=False),
    Column('modelo_embedding', String(150), nullable=False),
    Column('curso', String(160), nullable=False, default=''),
    Column('periodo', String(80), nullable=False, default=''),
    Column('ano', Integer),
    Column('inicio', Date), Column('fim', Date),
    Column('url_oficial', String(1000), nullable=False, default=''),
)
trechos = Table(
    'rag_trecho', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('versao_id', ForeignKey('rag_versao.id'), nullable=False, index=True),
    Column('pagina', Integer), Column('texto', Text, nullable=False),
    Column('embedding', LargeBinary, nullable=False),
)
