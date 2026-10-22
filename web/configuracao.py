import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from pathlib import Path
from seguranca.totp import chave_binaria
import config


@dataclass(frozen=True)
class ConfigWeb:
    origem: str = 'http://127.0.0.1:8000'
    usuario: str = 'admin'
    senha_hash: str = field(default='', repr=False)
    totp_segredo: str = field(default='', repr=False)
    seguranca_db: str = str(Path(__file__).resolve().parents[1] / 'runtime/seguranca.sqlite3')
    ttl: int = 3600
    max_upload: int = 25 * 1024 * 1024
    prazo: float = 120

    def __post_init__(self):
        """Valide a configuração construída e lance ValueError se os parâmetros forem inválidos."""
        url = urlsplit(self.origem)
        if url.scheme not in {'http', 'https'} or not url.hostname or url.path:
            raise ValueError('APP_ORIGIN precisa conter apenas protocolo, host e porta.')
        if url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', 'testserver'}:
            raise ValueError('Use HTTPS para atendimento fora da máquina local.')
        if url.username or url.password or url.query or url.fragment:
            raise ValueError('APP_ORIGIN não aceita credenciais, query ou fragmento.')
        validar_parametros(self)

    @property
    def seguro(self):
        """Informe se a origem configurada utiliza HTTPS."""
        return self.origem.startswith('https://')

    @classmethod
    def ambiente(cls):
        """Construa configuração web a partir das variáveis do ambiente."""
        return cls(origem=os.getenv('APP_ORIGIN', cls.origem).rstrip('/'),
                   usuario=os.getenv('ADMIN_USUARIO', 'admin'),
                   senha_hash=os.getenv('ADMIN_SENHA_HASH', ''),
                   prazo=config.RAG_TEMPO_GERACAO, totp_segredo=os.getenv('ADMIN_TOTP_SECRET', ''),
                   seguranca_db=os.getenv('SEGURANCA_DB', cls.seguranca_db))


def validar_parametros(config):
    """Valide prazos e segredo TOTP antes de iniciar o atendimento."""
    if config.ttl <= 0 or config.prazo <= 0:
        raise ValueError('Prazos devem ser positivos.')
    if config.totp_segredo:
        chave_binaria(config.totp_segredo)
