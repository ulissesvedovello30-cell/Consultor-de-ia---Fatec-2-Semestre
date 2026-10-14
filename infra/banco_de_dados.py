import asyncio
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

from mysql.connector import pooling, Error as MySQLError

from dominio.erros import ErroBancoDeDados

logger = logging.getLogger(__name__)

_TAMANHO_MAXIMO_POOL = 32  # limite do pool do mysql-connector


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
    nome_pool: str = "consultor_ia"

    def __post_init__(self) -> None:
        for nome in ("host", "usuario", "database"):
            if not getattr(self, nome):
                raise ValueError(f"Configuração do banco inválida: '{nome}' é obrigatório.")
        if not 1 <= self.porta <= 65535:
            raise ValueError("Configuração do banco inválida: 'porta' deve estar entre 1 e 65535.")
        if not 1 <= self.tamanho_pool <= _TAMANHO_MAXIMO_POOL:
            raise ValueError(
                f"Configuração do banco inválida: 'tamanho_pool' deve estar entre 1 e {_TAMANHO_MAXIMO_POOL}."
            )
        if self.timeout_conexao <= 0 or self.timeout_pool <= 0:
            raise ValueError("Configuração do banco inválida: os timeouts devem ser maiores que zero.")


class BancoDeDados:
    def __init__(self, config: ConfigBanco):
        self._config = config
        self._pool: pooling.MySQLConnectionPool | None = None
        # O pool do mysql-connector não espera: com todas as conexões em uso,
        # get_connection() falha na hora. Este semáforo faz o excedente esperar a vez.
        self._vagas: threading.BoundedSemaphore | None = None
        # Serializa conectar()/desconectar() entre si.
        self._ciclo_de_vida = threading.Lock()

    def conectar(self) -> None:
        """Cria o pool de conexões. Chame uma vez na inicialização."""
        with self._ciclo_de_vida:
            if self._pool is not None:
                return
            try:
                pool = pooling.MySQLConnectionPool(
                    pool_name=self._config.nome_pool,
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
            # _vagas antes de _pool: quem enxerga o pool sempre enxerga o semáforo.
            self._vagas = threading.BoundedSemaphore(self._config.tamanho_pool)
            self._pool = pool

    def desconectar(self) -> None:
        """Encerra o pool: bloqueia novas operações, espera as que estão em andamento
        (até timeout_pool por vaga) e fecha as conexões livres."""
        with self._ciclo_de_vida:
            pool, vagas = self._pool, self._vagas
            if pool is None or vagas is None:
                return
            # Novas operações passam a receber "Banco não conectado".
            self._pool = None
            self._vagas = None

            # Pegar todas as vagas = todas as operações em andamento já terminaram.
            # As vagas não são devolvidas: este semáforo não será mais usado.
            for _ in range(self._config.tamanho_pool):
                if not vagas.acquire(timeout=self._config.timeout_pool):
                    logger.warning("Encerrando o banco com operações ainda em andamento")
                    break

            self._fechar_conexoes(pool)

    @staticmethod
    def _fechar_conexoes(pool: "pooling.MySQLConnectionPool") -> None:
        """Fecha as conexões físicas do pool (melhor esforço).

        O mysql-connector não tem método público para isso; usa o interno
        _remove_connections quando existir. Se não existir ou falhar, as conexões
        são fechadas quando o objeto do pool for coletado ou o processo terminar.
        """
        remover = getattr(pool, "_remove_connections", None)
        if remover is None:
            return
        try:
            remover()
        except Exception:
            logger.warning("Não foi possível fechar todas as conexões do pool", exc_info=True)

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

        É síncrono (bloqueante). Em código async, use consultar_async.
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

        Qualquer falha antes do commit desfaz a transação (rollback).
        É síncrono (bloqueante). Em código async, use executar_async.
        """
        try:
            with self._conexao() as conexao:
                cursor = conexao.cursor()
                try:
                    cursor.execute(query, parametros)
                    conexao.commit()
                    return cursor.rowcount
                except BaseException:
                    self._rollback_seguro(conexao)
                    raise
                finally:
                    cursor.close()
        except MySQLError as e:
            raise ErroBancoDeDados("Erro ao executar comando") from e

    @staticmethod
    def _rollback_seguro(conexao) -> None:
        """Rollback que nunca esconde a exceção original (a conexão pode estar quebrada)."""
        try:
            conexao.rollback()
        except Exception:
            logger.warning("Rollback falhou; a conexão pode estar inutilizável", exc_info=True)

    async def consultar_async(self, query: str, parametros: tuple = ()) -> list[dict]:
        """consultar() em thread separada, sem bloquear o event loop."""
        return await asyncio.to_thread(self.consultar, query, parametros)

    async def executar_async(self, query: str, parametros: tuple = ()) -> int:
        """executar() em thread separada, sem bloquear o event loop."""
        return await asyncio.to_thread(self.executar, query, parametros)

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.desconectar()
