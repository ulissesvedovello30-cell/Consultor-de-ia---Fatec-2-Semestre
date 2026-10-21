import numpy as np
from sqlalchemy import MetaData, Table, delete, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError, SQLAlchemyError

from dominio.erros import ErroBancoDeDados
from dominio.trecho_documento import TrechoDocumento

_NOME_TABELA = "trecho_documento"
_TRECHOS_POR_INSERT = 200
_DTYPE_VETOR = "<f4"  # float32 little-endian explícito: o BLOB não depende da máquina


class RepositorioTrechos:
    """Guarda os trechos dos documentos e seus vetores na tabela `trecho_documento` (ver schema_rag.sql).

    A tabela é lida do próprio banco (reflexão), nunca criada por aqui: se ela não
    existir, o erro diz para rodar o schema_rag.sql.

    `carregar` traz tudo para a memória: serve bem para algumas dezenas de milhares
    de trechos. Passando disso, vale trocar por um banco vetorial.
    """

    def __init__(self, engine: Engine, tabela: Table | None = None):
        self._engine = engine
        self._tabela = tabela if tabela is not None else self._refletir(engine)

    @staticmethod
    def _refletir(engine: Engine) -> Table:
        try:
            return Table(_NOME_TABELA, MetaData(), autoload_with=engine)
        except NoSuchTableError as e:
            raise ErroBancoDeDados(f"A tabela '{_NOME_TABELA}' não existe. Rode infra/schema_rag.sql no banco.") from e
        except SQLAlchemyError as e:
            raise ErroBancoDeDados("Não foi possível ler a estrutura do banco") from e

    def indexado(self, hash_arquivo: str, modelo_embedding: str) -> bool:
        t = self._tabela
        consulta = (
            select(t.c.id)
            .where(t.c.hash_arquivo == hash_arquivo, t.c.modelo_embedding == modelo_embedding)
            .limit(1)
        )
        try:
            with self._engine.connect() as conexao:
                return conexao.execute(consulta).first() is not None
        except SQLAlchemyError as e:
            raise ErroBancoDeDados("Erro ao consultar o banco") from e

    def substituir_arquivo(
        self,
        hash_arquivo: str,
        modelo_embedding: str,
        trechos: list[TrechoDocumento],
        embeddings: np.ndarray,
    ) -> None:
        """Apaga o que havia do arquivo e grava de novo, tudo numa transação: ou troca por inteiro, ou nada muda."""
        if len(trechos) != len(embeddings):
            raise ValueError("Cada trecho precisa de exatamente um vetor.")

        linhas = [
            {
                "hash_arquivo": hash_arquivo,
                "arquivo": trecho.arquivo,
                "pagina": trecho.pagina,
                "texto": trecho.texto,
                "modelo_embedding": modelo_embedding,
                "embedding": vetor.astype(_DTYPE_VETOR).tobytes(),
            }
            for trecho, vetor in zip(trechos, embeddings)
        ]
        try:
            with self._engine.begin() as conexao:  # commit ao sair; rollback se der erro
                conexao.execute(delete(self._tabela).where(self._tabela.c.hash_arquivo == hash_arquivo))
                for inicio in range(0, len(linhas), _TRECHOS_POR_INSERT):
                    conexao.execute(insert(self._tabela), linhas[inicio : inicio + _TRECHOS_POR_INSERT])
        except SQLAlchemyError as e:
            raise ErroBancoDeDados("Erro ao gravar os trechos no banco") from e

    def carregar(self, modelo_embedding: str) -> tuple[list[TrechoDocumento], np.ndarray]:
        """Todos os trechos do modelo e a matriz de vetores (uma linha por trecho, mesma ordem)."""
        t = self._tabela
        consulta = (
            select(t.c.arquivo, t.c.pagina, t.c.texto, t.c.embedding)
            .where(t.c.modelo_embedding == modelo_embedding)
            .order_by(t.c.id)
        )
        try:
            with self._engine.connect() as conexao:
                linhas = conexao.execute(consulta).all()
        except SQLAlchemyError as e:
            raise ErroBancoDeDados("Erro ao ler os trechos do banco") from e

        if not linhas:
            return [], np.empty((0, 0), dtype=np.float32)

        trechos = [TrechoDocumento(arquivo=l.arquivo, pagina=l.pagina, texto=l.texto) for l in linhas]
        matriz = np.vstack([np.frombuffer(l.embedding, dtype=_DTYPE_VETOR) for l in linhas])
        return trechos, matriz.astype(np.float32)
