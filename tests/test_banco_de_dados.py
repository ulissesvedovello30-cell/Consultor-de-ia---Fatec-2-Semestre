"""Persistência SQLite real, inicialização e limites dos perfis disponíveis."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import pytest
from sqlalchemy import inspect, select, func, insert
from sqlalchemy.exc import IntegrityError
from dominio.erros import ErroBancoDeDados
from dominio.trecho_documento import TrechoDocumento
from infra.banco_de_dados import criar_engine
from infra.esquema import documentos, versoes, trechos
from infra.repositorio_trechos import RepositorioTrechos


def test_cria_esquema_e_preserva_documento_apos_reabrir(tmp_path):
    path = tmp_path / 'persistente' / 'acervo.sqlite3'
    engine = criar_engine('mvp', str(path))
    repo = RepositorioTrechos(engine)
    repo.substituir_arquivo('hash', 'modelo', [TrechoDocumento('a.txt', 1, 'Cursos gratuitos.')], np.ones((1, 768)))
    identidade = repo.listar()[0]['id_1']
    engine.dispose()
    engine = criar_engine('mvp', str(path))
    assert {'rag_documento', 'rag_versao', 'rag_trecho', 'rag_inicializacao'} <= set(inspect(engine).get_table_names())
    assert RepositorioTrechos(engine).listar()[0]['id_1'] == identidade
    assert path.stat().st_size > 0
    engine.dispose()


def test_chaves_estrangeiras_journal_e_rollback(tmp_path):
    engine = criar_engine('mvp', str(tmp_path / 'acervo.db'))
    with engine.connect() as c:
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        assert c.exec_driver_sql('PRAGMA journal_mode').scalar() == 'wal'
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(insert(trechos).values(versao_id='ausente', texto='texto', embedding=b'1'))
    with pytest.raises(RuntimeError), engine.begin() as c:
        c.execute(insert(documentos).values(id='teste', nome='teste.txt'))
        raise RuntimeError('cancelar')
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(documentos)) == 0
    engine.dispose()


def test_escritas_concorrentes_nao_deixam_versoes_orfas(tmp_path):
    path = str(tmp_path / 'acervo.db')
    engines = [criar_engine('mvp', path) for _ in range(2)]
    def publicar(i):
        repo = RepositorioTrechos(engines[i])
        for n in range(5):
            repo.substituir_arquivo(f'{i}-{n}', 'modelo', [TrechoDocumento('mesmo.txt', 1, f'Texto {i}-{n}')], np.ones((1, 768)))
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(publicar, range(2)))
    with engines[0].connect() as c:
        for table in (documentos, versoes, trechos):
            assert c.scalar(select(func.count()).select_from(table)) == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    for engine in engines: engine.dispose()


def test_caminho_relativo_independe_do_terminal(tmp_path, monkeypatch):
    import infra.sqlite as modulo
    monkeypatch.setattr(modulo, 'RAIZ', tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    engine = criar_engine('mvp', 'runtime/acervo.db')
    assert Path(engine.url.database) == tmp_path / 'runtime/acervo.db'
    engine.dispose()


@pytest.mark.parametrize('perfil,erro', [('postgres', NotImplementedError), ('mysql', ValueError), ('desconhecido', ValueError)])
def test_perfil_indisponivel_nao_cria_outro_banco(tmp_path, perfil, erro):
    path = tmp_path / 'nao_criar.db'
    with pytest.raises(erro): criar_engine(perfil, str(path))
    assert not path.exists()


@pytest.mark.parametrize('caminho', ['', ':memory:'])
def test_mvp_exige_arquivo_persistente(caminho):
    with pytest.raises(ErroBancoDeDados): criar_engine('mvp', caminho)


def test_arquivo_invalido_produz_erro_sanitizado(tmp_path):
    path = tmp_path / 'secreto.db'
    path.write_bytes(b'conteudo que nao e SQLite')
    with pytest.raises(ErroBancoDeDados) as erro: criar_engine('mvp', str(path))
    assert 'secreto' not in str(erro.value)
