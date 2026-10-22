from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine


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

    def __post_init__(self) -> None:
        """Valide a configuração construída e lance ValueError se os parâmetros forem inválidos."""
        for nome in ("host", "usuario", "database"):
            if not getattr(self, nome):
                raise ValueError(f"Configuração do banco inválida: '{nome}' é obrigatório.")
        if not 1 <= self.porta <= 65535:
            raise ValueError("Configuração do banco inválida: 'porta' deve estar entre 1 e 65535.")
        if not 1 <= self.tamanho_pool <= 32:
            raise ValueError("Configuração do banco inválida: 'tamanho_pool' deve estar entre 1 e 32.")
        if self.timeout_conexao <= 0 or self.timeout_pool <= 0:
            raise ValueError("Configuração do banco inválida: os timeouts devem ser maiores que zero.")


def criar_engine(config: ConfigBanco) -> Engine:
    """Usa tabelas já instaladas pelo schema_rag.sql. Não cria nem altera tabelas."""
    url = URL.create('mysql+mysqlconnector', username=config.usuario, password=config.senha,
                     host=config.host, port=config.porta, database=config.database,
                     query={'charset': config.charset})
    return create_engine(url, pool_size=config.tamanho_pool, max_overflow=0,
                         pool_timeout=config.timeout_pool, pool_pre_ping=True,
                         connect_args={'connection_timeout': config.timeout_conexao},
                         hide_parameters=True)
