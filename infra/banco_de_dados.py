from contextlib import contextmanager
from dataclasses import dataclass, field

import mysql.connector
from mysql.connector import pooling, Error as MySQLError


class ErroBancoDeDados(Exception):
    """Erro de infraestrutura do banco, sem vazar detalhes do driver."""


@dataclass(frozen=True)
class ConfigBanco:
    host: str
    usuario: str
    senha: str = field(repr=False)  # não aparece em logs/repr
    database: str
    porta: int = 3306
    tamanho_pool: int = 5


class BancoDeDados:
    def __init__(self, config: ConfigBanco):
        self._config = config
        self._pool: pooling.MySQLConnectionPool | None = None

    def conectar(self) -> None:
        """Cria o pool de conexões. Chame uma vez na inicialização."""
        if self._pool is not None:
            return
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="consultor_ia",
                pool_size=self._config.tamanho_pool,
                host=self._config.host,
                port=self._config.porta,
                user=self._config.usuario,
                password=self._config.senha,
                database=self._config.database,
            )
        except MySQLError as e:
            raise ErroBancoDeDados("Falha ao criar pool de conexões") from e

    def desconectar(self) -> None:
        """Descarta a referência ao pool (conexões livres são fechadas pelo GC/driver)."""
        self._pool = None

    @contextmanager
    def _conexao(self):
        """Pega uma conexão do pool e garante que ela volte, mesmo com erro."""
        if self._pool is None:
            raise ErroBancoDeDados("Banco não conectado. Chame conectar() primeiro.")
        try:
            conexao = self._pool.get_connection()
        except MySQLError as e:
            raise ErroBancoDeDados("Sem conexão disponível no pool") from e
        try:
            conexao.ping(reconnect=True, attempts=2, delay=1)  # evita "server has gone away"
            yield conexao
        finally:
            conexao.close()  # em pool, close() devolve a conexão ao pool

    def consultar(self, query: str, parametros: tuple = ()) -> list[dict]:
        """SELECT. Sempre use %s + parametros; nunca concatene valores na query."""
        try:
            with self._conexao() as conexao:
                cursor = conexao.cursor(dictionary=True)
                try:
                    cursor.execute(query, parametros)
                    return cursor.fetchall()
                finally:
                    cursor.close()
        except MySQLError as e:
            raise ErroBancoDeDados("Erro ao executar consulta") from e

    def executar(self, query: str, parametros: tuple = ()) -> int:
        """INSERT/UPDATE/DELETE. Faz commit e retorna as linhas afetadas."""
        try:
            with self._conexao() as conexao:
                cursor = conexao.cursor()
                try:
                    cursor.execute(query, parametros)
                    conexao.commit()
                    return cursor.rowcount
                except MySQLError:
                    conexao.rollback()
                    raise
                finally:
                    cursor.close()
        except MySQLError as e:
            raise ErroBancoDeDados("Erro ao executar comando") from e

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.desconectar()
