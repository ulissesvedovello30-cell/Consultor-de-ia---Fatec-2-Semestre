"""Limites duráveis em SQLite, isolados das tabelas do acervo e dos alunos."""
import math
import os
import secrets
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path
from seguranca.contratos import FalhaSeguranca, TentativasExcedidas

POLITICAS = ((5, 60), (10, 900), (30, 60))  # IP, conta declarada, serviço.
SCHEMA = '''
CREATE TABLE IF NOT EXISTS tentativa (chave TEXT NOT NULL, instante REAL NOT NULL);
CREATE INDEX IF NOT EXISTS tentativa_chave ON tentativa(chave, instante);
CREATE TABLE IF NOT EXISTS codigo_usado (chave TEXT PRIMARY KEY, passo INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS segredo (id INTEGER PRIMARY KEY CHECK(id=1), valor BLOB NOT NULL);
'''


class RepositorioLoginSQLite:
    """Mantenha cotas entre reinícios e serialize reservas entre processos locais."""

    def __init__(self, caminho):
        """Crie o esquema próprio no caminho informado; não acesse o MySQL."""
        self.caminho = str(Path(caminho).resolve())
        Path(self.caminho).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        preparar_arquivo(self.caminho)
        self._inicializar()

    def _inicializar(self):
        """Crie tabelas e segredo estável atomicamente com permissões restritas."""
        try:
            with closing(sqlite3.connect(self.caminho, timeout=2, isolation_level=None)) as banco:
                banco.execute('PRAGMA journal_mode=WAL')
                banco.executescript(SCHEMA)
                banco.execute('INSERT OR IGNORE INTO segredo VALUES (1, ?)', (secrets.token_bytes(32),))
        except (sqlite3.Error, OSError):
            raise FalhaSeguranca('Não foi possível preparar a proteção do login.') from None

    @contextmanager
    def transacao(self):
        """Abra transação exclusiva de escrita e converta falhas sem expor caminhos."""
        try:
            with sqlite3.connect(self.caminho, timeout=2, isolation_level=None) as banco:
                banco.execute('BEGIN IMMEDIATE')
                yield banco
                banco.commit()
        except sqlite3.Error:
            raise FalhaSeguranca('Proteção do login indisponível.') from None
        finally:
            if 'banco' in locals():
                banco.close()

    def segredo(self):
        """Retorne o segredo de HMAC mantido somente no armazenamento local."""
        with self.transacao() as banco:
            return banco.execute('SELECT valor FROM segredo WHERE id=1').fetchone()[0]

    def reservar(self, chaves, agora):
        """Reserve cotas por IP, conta e serviço; falhas não prolongam o bloqueio."""
        with self.transacao() as banco:
            banco.execute('DELETE FROM tentativa WHERE instante <= ?', (agora - 900,))
            for chave, politica in zip(chaves, POLITICAS, strict=True):
                conferir_cota(banco, chave, agora, *politica)
            banco.executemany('INSERT INTO tentativa VALUES (?, ?)', [(c, agora) for c in chaves])

    def consumir_codigo(self, chave, passo):
        """Consuma o código uma só vez, inclusive entre instâncias do serviço."""
        with self.transacao() as banco:
            linha = banco.execute('SELECT passo FROM codigo_usado WHERE chave=?', (chave,)).fetchone()
            if linha and passo <= linha[0]:
                return False
            banco.execute('INSERT INTO codigo_usado VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET passo=excluded.passo', (chave, passo))
            return True

    def limpar(self, agora):
        """Apague tentativas após 15 minutos sem depender de novos acessos ao login."""
        with self.transacao() as banco:
            banco.execute('DELETE FROM tentativa WHERE instante <= ?', (agora - 900,))


def conferir_cota(banco, chave, agora, limite, janela):
    """Lance TentativasExcedidas se a janela já contiver o número máximo de tentativas."""
    linhas = banco.execute('SELECT instante FROM tentativa WHERE chave=? AND instante>? ORDER BY instante',
                          (chave, agora - janela)).fetchall()
    if len(linhas) >= limite:
        raise TentativasExcedidas(math.ceil(linhas[0][0] + janela - agora))


def preparar_arquivo(caminho):
    """Crie armazenamento com modo privado antes de gravar qualquer segredo."""
    try:
        descritor = os.open(caminho, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descritor)
        Path(caminho).chmod(0o600)
    except OSError:
        raise FalhaSeguranca('Não foi possível proteger o armazenamento do login.') from None
