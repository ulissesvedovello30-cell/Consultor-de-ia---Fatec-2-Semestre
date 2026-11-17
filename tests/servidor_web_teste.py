"""Servidor exclusivamente para testes DOM. Nunca usar em produção."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn
from sqlalchemy import create_engine
from tests.apoio_acervo import montar_acervo_teste
from web.aplicacao import criar_app
from web.configuracao import ConfigWeb
from web.senhas import gerar_hash


@contextmanager
def fabrica():
    with TemporaryDirectory() as pasta:
        engine = create_engine('sqlite:///' + str(Path(pasta) / 'teste.db'))
        try:
            yield montar_acervo_teste(engine)
        finally:
            engine.dispose()


if __name__ == '__main__':
    config = ConfigWeb(origem='http://127.0.0.1:8765', senha_hash=gerar_hash('senha-apenas-teste'))
    app = criar_app(fabrica, config, 'teste')
    uvicorn.run(app, host='127.0.0.1', port=8765, access_log=False)
