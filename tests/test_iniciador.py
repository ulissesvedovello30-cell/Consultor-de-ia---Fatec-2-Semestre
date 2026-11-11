"""Preparação do ambiente sem chamadas ao Gemini."""
from pathlib import Path
from types import SimpleNamespace
import os
import shutil
import subprocess
import sys
import pytest
import main as inicio


def test_comando_usa_python_virtual_sem_shell_e_remove_pythonpath(tmp_path, monkeypatch):
    chamadas = []
    python = tmp_path / 'pasta com espacos' / 'python'
    monkeypatch.setenv('PYTHONPATH', 'dependencias-externas')
    monkeypatch.setenv('PYTHONHOME', 'outra-instalacao')
    monkeypatch.setattr(inicio.subprocess, 'run', lambda cmd, **kw: chamadas.append((cmd, kw)))
    inicio.executar(python, ['servidor.py', '--abrir'])
    cmd, kw = chamadas[0]
    assert cmd == [str(python), 'servidor.py', '--abrir']
    assert kw['check'] and not kw.get('shell', False)
    assert 'PYTHONPATH' not in kw['env'] and 'PYTHONHOME' not in kw['env']


def test_env_existente_nao_e_sobrescrito(tmp_path, monkeypatch):
    monkeypatch.setattr(inicio, 'RAIZ', tmp_path)
    (tmp_path / '.env.example').write_text('GEMINI_API_KEY=\n')
    (tmp_path / '.env').write_text('GEMINI_API_KEY=segredo-preservado\n')
    inicio.preparar_env()
    assert (tmp_path / '.env').read_text() == 'GEMINI_API_KEY=segredo-preservado\n'


def test_erro_na_instalacao_impede_inicio(monkeypatch):
    chamadas = []
    monkeypatch.setattr(inicio, 'argumentos', lambda: SimpleNamespace(dev=False))
    monkeypatch.setattr(inicio, 'preparar_venv', lambda: Path('python-teste'))
    monkeypatch.setattr(inicio, 'verificar_venv', lambda p: None)
    monkeypatch.setattr(inicio, 'garantir_pip', lambda p: None)
    def falhar(*args):
        raise subprocess.CalledProcessError(1, ['pip'])
    monkeypatch.setattr(inicio, 'preparar_dependencias', falhar)
    monkeypatch.setattr(inicio, 'iniciar_servidor', lambda *args: chamadas.append('servidor'))
    with pytest.raises(subprocess.CalledProcessError): inicio.main()
    assert not chamadas


def test_dependencias_de_execucao_e_testes_sao_separadas(monkeypatch):
    chamadas = []
    monkeypatch.setattr(inicio, 'executar', lambda p, args: chamadas.append(args))
    inicio.instalar(Path('python'), False)
    assert str(inicio.RAIZ / 'requirements.txt') in chamadas[0]
    assert str(inicio.RAIZ / 'requirements-ngrok.txt') in chamadas[0]
    assert str(inicio.RAIZ / 'requirements-dev.txt') not in chamadas[0]
    inicio.instalar(Path('python'), True)
    assert str(inicio.RAIZ / 'requirements-dev.txt') in chamadas[2]


def test_preparacao_sem_servidor_e_ngrok_so_quando_pedido(monkeypatch):
    chamadas = []
    monkeypatch.setattr(inicio, 'executar', lambda p, args: chamadas.append(args))
    inicio.iniciar_servidor(Path('python'), SimpleNamespace(preparar=True, ngrok=False))
    assert not chamadas
    inicio.iniciar_servidor(Path('python'), SimpleNamespace(preparar=False, ngrok=False))
    assert chamadas[-1] == ['servidor.py', '--abrir']
    inicio.iniciar_servidor(Path('python'), SimpleNamespace(preparar=False, ngrok=True))
    assert chamadas[-1] == ['servidor.py', '--abrir', '--ngrok']


def test_venv_real_reutilizada_e_inicio_em_pasta_com_espacos(tmp_path):
    pasta = tmp_path / 'projeto com espacos'
    pasta.mkdir()
    shutil.copyfile(inicio.RAIZ / 'main.py', pasta / 'main.py')
    for nome in ('requirements.txt', 'requirements-ngrok.txt'):
        (pasta / nome).write_text('')
    (pasta / '.env.example').write_text('GEMINI_API_KEY=\n')
    (pasta / 'servidor.py').write_text('from pathlib import Path\nimport sys\nassert sys.prefix != sys.base_prefix\nPath("iniciou").write_text(sys.prefix)\n')
    comando = [sys.executable, str(pasta / 'main.py')]
    primeiro = subprocess.run([*comando, '--preparar'], cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert primeiro.returncode == 0, primeiro.stdout + primeiro.stderr
    assert not (pasta / 'iniciou').exists()
    cfg = pasta / '.venv' / 'pyvenv.cfg'
    momento = cfg.stat().st_mtime_ns
    segundo = subprocess.run(comando, cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert segundo.returncode == 0, segundo.stdout + segundo.stderr
    assert 'Conferindo dependências do projeto...' not in segundo.stdout
    assert cfg.stat().st_mtime_ns == momento
    assert Path((pasta / 'iniciou').read_text()).resolve() == (pasta / '.venv').resolve()
