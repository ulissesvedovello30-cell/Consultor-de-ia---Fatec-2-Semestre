"""Prepare o ambiente virtual e inicie o chatbot sem ativação manual."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

RAIZ = Path(__file__).resolve().parent
AMBIENTE = RAIZ / '.venv'


def argumentos():
    """Leia opções de preparação e execução.

    Returns:
        Namespace: Opções escolhidas no terminal.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparar', action='store_true', help='Prepare o ambiente sem iniciar o servidor.')
    parser.add_argument('--dev', action='store_true', help='Inclua também as dependências dos testes Python.')
    parser.add_argument('--ngrok', action='store_true', help='Inicie com o túnel configurado no projeto.')
    return parser.parse_args()


def python_virtual():
    """Localize o interpretador do ambiente no sistema atual.

    Returns:
        Path: Executável Python dentro da .venv.
    """
    relativos = {'nt': 'Scripts/python.exe', 'posix': 'bin/python'}
    return AMBIENTE / relativos[os.name]


def preparar_venv():
    """Crie a .venv somente se seu interpretador não existir.

    Returns:
        Path: Interpretador virtual pronto para verificação.

    Raises:
        OSError: Se não for possível criar o ambiente.
    """
    python = python_virtual()
    try:
        python.stat()
    except FileNotFoundError:
        print('Criando o ambiente virtual...', flush=True)
        venv.EnvBuilder(with_pip=True).create(AMBIENTE)
    return python


def executar(python, argumentos):
    """Execute um comando no ambiente virtual, interrompendo em caso de erro.

    Args:
        python (Path): Interpretador selecionado.
        argumentos (list[str]): Argumentos sem interpolação de shell.

    Raises:
        CalledProcessError: Se o comando retornar falha.
        OSError: Se o executável estiver indisponível.
    """
    ambiente = dict(os.environ, VIRTUAL_ENV=str(AMBIENTE), PYTHONNOUSERSITE='1')
    ambiente.pop('PYTHONPATH', None)
    ambiente.pop('PYTHONHOME', None)
    ambiente['PATH'] = str(python.parent) + os.pathsep + ambiente.get('PATH', '')
    subprocess.run([str(python), *argumentos], cwd=RAIZ, env=ambiente, check=True)


def verificar_venv(python):
    """Confirme isolamento e versão antes de instalar qualquer pacote.

    Args:
        python (Path): Interpretador encontrado na .venv.

    Raises:
        CalledProcessError: Se o ambiente estiver quebrado ou usar Python antigo.
    """
    codigo = ('import sys; from pathlib import Path; '
              'valido = sys.version_info >= (3, 12) and sys.prefix != sys.base_prefix '
              'and Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve(); '
              'print("Python do ambiente:", sys.version.split()[0]); '
              'sys.exit(0 if valido else "Ambiente invalido. Use Python 3.15 e recrie somente a .venv.")')
    executar(python, ['-I', '-c', codigo, str(AMBIENTE)])


def verificar_pip(python):
    """Confirme que o pip funciona no interpretador da venv.

    Args:
        python (Path): Interpretador virtual já validado.

    Raises:
        CalledProcessError: Se o pip estiver ausente ou quebrado.
    """
    subprocess.run([str(python), '-I', '-m', 'pip', '--version'], cwd=RAIZ,
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def garantir_pip(python):
    """Recupere o pip ausente antes de conferir as dependências.

    Args:
        python (Path): Interpretador da venv, sem alterar o Python global.

    Raises:
        ValueError: Se o Python não conseguir recuperar o instalador.
    """
    try:
        verificar_pip(python)
    except subprocess.CalledProcessError:
        print('Recuperando o pip da .venv...', flush=True)
        try:
            executar(python, ['-I', '-m', 'ensurepip', '--upgrade', '--default-pip'])
            verificar_pip(python)
        except subprocess.CalledProcessError:
            raise ValueError('Não foi possível recuperar o pip. Repare o Python com suporte a pip/ensurepip e rode o main novamente.') from None


def requirements(desenvolvimento):
    """Liste os arquivos de dependências usados neste modo de execução.

    Args:
        desenvolvimento (bool): Inclui os pacotes usados pelos testes.

    Returns:
        list[str]: Nomes dos arquivos de requisitos.
    """
    arquivos = ['requirements.txt', 'requirements-ngrok.txt']
    return arquivos + (['requirements-dev.txt'] if desenvolvimento else [])


def assinatura(python, arquivos):
    """Identifique os requisitos e pacotes efetivos do ambiente virtual.

    Args:
        python (Path): Interpretador da .venv.
        arquivos (list[str]): Requisitos usados nesta execução.

    Returns:
        str: Resumo da versão do Python, requisitos e pacotes instalados.
    """
    codigo = ('import sys; from importlib.metadata import distributions; '
              'print(sys.version); print(sorted((d.metadata["Name"], d.version) for d in distributions()))')
    pacotes = subprocess.check_output([str(python), '-I', '-c', codigo], cwd=RAIZ)
    resumo = hashlib.sha256(pacotes)
    for nome in arquivos:
        resumo.update(nome.encode() + b'\0' + (RAIZ / nome).read_bytes() + b'\0')
    return resumo.hexdigest()


def preparar_dependencias(python, desenvolvimento):
    """Reutilize dependências já conferidas ou atualize a instalação.

    Args:
        python (Path): Interpretador já validado da .venv.
        desenvolvimento (bool): Inclui dependências extras de desenvolvimento.
    """
    arquivos = requirements(desenvolvimento)
    registro = AMBIENTE / ('.deps-dev' if desenvolvimento else '.deps')
    try:
        if registro.read_text(encoding='ascii') == assinatura(python, arquivos):
            return
    except (FileNotFoundError, UnicodeError):
        pass
    instalar(python, desenvolvimento)
    registro.write_text(assinatura(python, arquivos), encoding='ascii')


def instalar(python, desenvolvimento):
    """Confira requirements e instale os pacotes ausentes no ambiente virtual.

    Args:
        python (Path): Interpretador da .venv.
        desenvolvimento (bool): Inclua os testes Python quando solicitado.

    Raises:
        CalledProcessError: Se a instalação ou verificação de dependências falhar.
    """
    arquivos = requirements(desenvolvimento)
    opcoes = [item for nome in arquivos for item in ('-r', str(RAIZ / nome))]
    print('Conferindo dependências do projeto...', flush=True)
    executar(python, ['-m', 'pip', '--isolated', '--disable-pip-version-check', 'install', *opcoes])
    executar(python, ['-m', 'pip', '--isolated', 'check'])


def preparar_env():
    """Crie o modelo de configuração sem sobrescrever credenciais existentes.

    Raises:
        OSError: Se o modelo ou o destino estiver indisponível.
    """
    destino = RAIZ / '.env'
    modelo = (RAIZ / '.env.example').read_bytes()
    try:
        descritor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(descritor, 'wb') as arquivo:
        arquivo.write(modelo)
    print('Arquivo .env criado. Configure GEMINI_API_KEY antes do primeiro atendimento.', flush=True)


def iniciar_servidor(python, opcoes):
    """Abra o servidor apenas após preparar o ambiente com sucesso.

    Args:
        python (Path): Interpretador da .venv.
        opcoes: Preferências recebidas pela linha de comando.
    """
    try:
        (True,).index(not opcoes.preparar)
    except ValueError:
        print('Ambiente preparado. Configure o .env e o administrador conforme o LEIA-ME.md.')
        return
    tunel = {False: [], True: ['--ngrok']}[opcoes.ngrok]
    executar(python, ['servidor.py', '--abrir', *tunel])


def main():
    """Prepare os recursos locais e execute o projeto na ordem necessária."""
    opcoes = argumentos()
    python = preparar_venv()
    verificar_venv(python)
    garantir_pip(python)
    preparar_dependencias(python, opcoes.dev)
    preparar_env()
    iniciar_servidor(python, opcoes)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as erro:
        print('Etapa interrompida. Confira a mensagem acima; dependências exigem internet e o chatbot exige Gemini.')
        raise SystemExit(erro.returncode or 1) from None
    except (OSError, ValueError) as erro:
        print(f'Não foi possível preparar ou iniciar o projeto: {erro}')
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print('\nExecução encerrada.')
        raise SystemExit(130) from None
