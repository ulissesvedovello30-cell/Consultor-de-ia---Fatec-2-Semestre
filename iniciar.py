"""Menu local para iniciar o site pelo terminal do VS Code ou outro terminal."""
import subprocess
import sys
from pathlib import Path


def main():
    """Peça o modo e execute o servidor usando o mesmo interpretador Python."""
    print('1 — Demonstração (SQLite fictício, sem chave)\n2 — Oficial (MySQL + Gemini)\n0 — Sair')
    escolhas = {'1': ['--demo', '--abrir'], '2': ['--abrir'], '0': None}
    try:
        argumentos = escolhas[input('Escolha [1/2/0]: ').strip()]
    except KeyError:
        print('Opção inválida. Execute novamente e escolha 1, 2 ou 0.')
        return
    if argumentos is not None:
        subprocess.run([sys.executable, 'servidor.py', *argumentos], cwd=Path(__file__).parent, check=False)


if __name__ == '__main__':
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print('\nEncerrado.')
