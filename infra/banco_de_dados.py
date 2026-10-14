import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

from mysql.connector import pooling, Error as MySQLError

from dominio.erros import ErroBancoDeDados


@dataclass(frozen=True)
class ConfigBanco:
    host: str
    usuario: str
    senha: str = field(repr=False)  # não aparece em logs/repr
    database: str
    porta: int = 3306
    tamanho_pool: int = 5
    charset: str = "utf8mb4"  # acentos e emojis
    timeout_conexao: int = 10  # segundos; evita ficar pendurado se a rede cair
    timeout_pool: float = 10.0  # segundos esperando uma conexão livre do pool


class BancoDeDados:
    def __init__(self, config: ConfigBanco):
        self._config = config
        self._pool: pooling.MySQLConnectionPool | None = None
        # O pool do mysql-connector não espera: com todas as conexões em uso,
        # get_connection() falha na hora. Este semáforo faz o excedente esperar a vez.
        self._vagas: threading.BoundedSemaphore | None = None

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
                charset=self._config.charset,
                connection_timeout=self._config.timeout_conexao,
            )
        except MySQLError as e:
            raise ErroBancoDeDados("Falha ao criar pool de conexões") from e
        self._vagas = threading.BoundedSemaphore(self._config.tamanho_pool)

    def desconectar(self) -> None:
        """Descarta a referência ao pool (conexões livres são fechadas pelo GC/driver)."""
        self._pool = None
        self._vagas = None

    @contextmanager
    def _conexao(self):
        """Pega uma conexão do pool e garante que ela volte, mesmo com erro."""
        # Cópias locais: desconectar() em outra thread não pode zerar isso no meio do uso.
        pool, vagas = self._pool, self._vagas
        if pool is None or vagas is None:
            raise ErroBancoDeDados("Banco não conectado. Chame conectar() primeiro.")

        if not vagas.acquire(timeout=self._config.timeout_pool):
            raise ErroBancoDeDados("Tempo esgotado esperando uma conexão livre")
        try:
            try:
                conexao = pool.get_connection()
            except MySQLError as e:
                raise ErroBancoDeDados("Sem conexão disponível no pool") from e
            try:
                conexao.ping(reconnect=True, attempts=2, delay=1)  # evita "server has gone away"
                yield conexao
            finally:
                conexao.close()  # em pool, close() devolve a conexão ao pool
        finally:
            vagas.release()  # só depois de devolver a conexão, para o próximo achar uma livre

    def consultar(self, query: str, parametros: tuple = ()) -> list[dict]:
        """SELECT. Sempre use %s + parametros; nunca concatene valores na query.

        É síncrono (bloqueante): em código async, chame com asyncio.to_thread.
        """
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
        """INSERT/UPDATE/DELETE. Faz commit e retorna as linhas afetadas.

        É síncrono (bloqueante): em código async, chame com asyncio.to_thread.
        """
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
