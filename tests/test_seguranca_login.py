"""Regressões de força bruta, persistência, concorrência e segundo fator."""
import base64
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from seguranca.armazenamento import RepositorioLoginSQLite
from seguranca.autenticacao import AutenticadorSecretaria
from seguranca.contratos import TentativasExcedidas, CredenciaisInvalidas, FalhaSeguranca, LoginIndisponivel
from seguranca.totp import codigo, verificar
from tests.test_web import cliente, SENHA

SEGREDO = base64.b32encode(b'12345678901234567890').decode()


def autenticador(tmp_path, *, secreto=SEGREDO, obrigatorio=True, instante=1234567890):
    repo = RepositorioLoginSQLite(tmp_path / 'login.db')
    config = SimpleNamespace(usuario='admin', senha_hash='hash', totp_segredo=secreto)
    return AutenticadorSecretaria(repo, config, repo.segredo(), lambda senha, hash_: senha == 'correta',
                                 obrigatorio, lambda: instante)


@pytest.mark.parametrize('segundos,esperado', [(59,'94287082'), (1111111109,'07081804'),
    (1111111111,'14050471'), (1234567890,'89005924'), (2000000000,'69279037'), (20000000000,'65353130')])
def test_totp_vetores_oficiais_rfc6238(segundos, esperado):
    assert codigo(SEGREDO, segundos // 30, 8) == esperado


def test_totp_janela_e_formato():
    assert verificar(SEGREDO, codigo(SEGREDO, 99), 3000) == 99
    assert verificar(SEGREDO, codigo(SEGREDO, 101), 3000) == 101
    assert verificar(SEGREDO, codigo(SEGREDO, 98), 3000) is None
    assert verificar(SEGREDO, '１２３４５６', 3000) is None


def test_totp_replay_negado_apos_reiniciar(tmp_path):
    auth = autenticador(tmp_path)
    otp = codigo(SEGREDO, 1234567890 // 30)
    auth.autenticar('ip1', 'admin', 'correta', otp)
    with pytest.raises(CredenciaisInvalidas):
        autenticador(tmp_path).autenticar('ip2', 'admin', 'correta', otp)


def test_oficial_nao_abre_sem_2fa_e_demo_pode_testar_senha(tmp_path):
    with pytest.raises(LoginIndisponivel):
        autenticador(tmp_path, secreto='').autenticar('ip', 'admin', 'correta', '')
    autenticador(tmp_path, secreto='', obrigatorio=False).autenticar('ip', 'admin', 'correta', '')


def test_senha_invalida_nao_consume_otp_valido(tmp_path):
    auth = autenticador(tmp_path)
    otp = codigo(SEGREDO, 1234567890 // 30)
    with pytest.raises(CredenciaisInvalidas):
        auth.autenticar('ip', 'admin', 'errada', otp)
    auth.autenticar('ip', 'admin', 'correta', otp)


def test_cota_ip_persiste_e_expira_sem_prorrogar_bloqueio(tmp_path):
    repo = RepositorioLoginSQLite(tmp_path / 'login.db')
    for _ in range(5):
        repo.reservar(('ip', 'conta', 'global'), 1000)
    for instante in (1001, 1030, 1059):
        with pytest.raises(TentativasExcedidas):
            RepositorioLoginSQLite(tmp_path / 'login.db').reservar(('ip', 'conta', 'global'), instante)
    repo.reservar(('ip', 'conta', 'global'), 1060)


def test_cota_conta_sobrevive_rotacao_de_ips(tmp_path):
    repo = RepositorioLoginSQLite(tmp_path / 'login.db')
    for i in range(10):
        repo.reservar((f'ip{i}', 'conta', 'global'), 1000)
    with pytest.raises(TentativasExcedidas) as captura:
        repo.reservar(('novo', 'conta', 'global'), 1001)
    assert captura.value.segundos == 899
    repo.reservar(('novo', 'conta', 'global'), 1900)


def test_cota_global_sobrevive_rotacao_de_ips_e_contas(tmp_path):
    repo = RepositorioLoginSQLite(tmp_path / 'login.db')
    for i in range(30):
        repo.reservar((f'ip{i}', f'conta{i}', 'global'), 1000)
    with pytest.raises(TentativasExcedidas):
        repo.reservar(('ip31', 'conta31', 'global'), 1001)


def test_reserva_atomica_sob_concorrencia(tmp_path):
    caminho = tmp_path / 'login.db'
    repos = [RepositorioLoginSQLite(caminho) for _ in range(12)]
    def reservar(repo):
        try:
            repo.reservar(('ip', 'conta', 'global'), 1000)
            return True
        except TentativasExcedidas:
            return False
    with ThreadPoolExecutor(max_workers=12) as executor:
        assert sum(executor.map(reservar, repos)) == 5


def test_falha_persistencia_nao_libera_autenticacao(tmp_path, monkeypatch):
    auth = autenticador(tmp_path)
    def indisponivel(*args, **kwargs):
        raise sqlite3.OperationalError('segredo-nao-expor')
    monkeypatch.setattr(sqlite3, 'connect', indisponivel)
    with pytest.raises(FalhaSeguranca, match='indisponível') as captura:
        auth.autenticar('ip', 'admin', 'correta', '123456')
    assert 'segredo' not in str(captura.value)


def test_hmac_nao_persiste_ip_conta_ou_otp_em_claro(tmp_path):
    auth = autenticador(tmp_path)
    with pytest.raises(CredenciaisInvalidas):
        auth.autenticar('198.51.100.100', 'administrador-sigilo', 'errada', '654321')
    with auth.repo.transacao() as banco:
        registros = banco.execute('SELECT chave FROM tentativa').fetchall()
    assert len(registros) == 3 and all(len(chave) == 64 for (chave,) in registros)
    assert auth.repo.segredo() == RepositorioLoginSQLite(tmp_path / 'login.db').segredo()


def test_cota_hashing_sem_fila(tmp_path):
    auth = autenticador(tmp_path)
    assert auth.vagas.acquire(False) and auth.vagas.acquire(False)
    with pytest.raises(LoginIndisponivel):
        auth.autenticar('ip', 'admin', 'correta', '123456')


def test_login_http_2fa_e_replay(cliente):
    auth = cliente.app.state.protecao_login
    object.__setattr__(auth.config, 'totp_segredo', SEGREDO)
    auth.exigir_2fa, auth.relogio = True, lambda: 1234567890
    assert cliente.get('/api/sessao').json()['exige_2fa']
    credenciais = {'usuario': 'admin', 'senha': SENHA}
    assert cliente.post('/api/admin/login', json=credenciais).status_code == 401
    credenciais['otp'] = codigo(SEGREDO, 1234567890 // 30)
    resposta = cliente.post('/api/admin/login', json=credenciais)
    assert resposta.status_code == 200
    cliente.headers['X-CSRF-Token'] = resposta.json()['csrf']
    assert cliente.post('/api/admin/logout').status_code == 200
    cliente.headers['X-CSRF-Token'] = cliente.get('/api/sessao').json()['csrf']
    assert cliente.post('/api/admin/login', json=credenciais).status_code == 401
    assert cliente.get('/api/admin/documentos').status_code == 401


def test_x_forwarded_for_falso_nao_contorna_limite(cliente):
    for i in range(5):
        resposta = cliente.post('/api/admin/login', headers={'X-Forwarded-For': f'198.51.100.{i}'},
                               json={'usuario': 'admin', 'senha': 'errada'})
        assert resposta.status_code == 401
    resposta = cliente.post('/api/admin/login', headers={'X-Forwarded-For': '203.0.113.1'},
                           json={'usuario': 'admin', 'senha': SENHA})
    assert resposta.status_code == 429 and int(resposta.headers['Retry-After']) > 0


def test_login_banco_indisponivel_retorna_503(cliente, monkeypatch):
    def falhar(*args):
        raise FalhaSeguranca('caminho-interno')
    monkeypatch.setattr(cliente.app.state.protecao_login.repo, 'reservar', falhar)
    resposta = cliente.post('/api/admin/login', json={'usuario': 'admin', 'senha': SENHA})
    assert resposta.status_code == 503 and 'caminho-interno' not in resposta.text
    assert cliente.get('/api/admin/documentos').status_code == 401


def test_arquivo_de_seguranca_tem_permissoes_restritas(tmp_path):
    import os
    if os.name != 'posix':
        pytest.skip('ACLs Windows precisam de validação no ambiente de destino.')
    caminho = tmp_path / 'privado' / 'login.db'
    repo = RepositorioLoginSQLite(caminho)
    assert caminho.stat().st_mode & 0o777 == 0o600
    assert caminho.parent.stat().st_mode & 0o777 == 0o700
    assert len(repo.segredo()) == 32
