import pytest

from infra.banco_de_dados import ConfigBanco, criar_engine


def _config(**mudancas):
    base = dict(host="localhost", usuario="root", senha="p@ss:w/rd#1", database="chatbot")
    return ConfigBanco(**{**base, **mudancas})


def test_engine_aponta_para_o_mysql_sem_conectar():
    engine = criar_engine(_config())  # só monta; a conexão abre na primeira consulta

    assert engine.dialect.name == "mysql" and engine.dialect.driver == "mysqlconnector"
    assert (engine.url.host, engine.url.port, engine.url.database) == ("localhost", 3306, "chatbot")
    assert engine.url.query["charset"] == "utf8mb4"


def test_senha_com_caracteres_especiais_chega_inteira_e_nao_aparece_no_texto_da_url():
    engine = criar_engine(_config())

    assert engine.url.password == "p@ss:w/rd#1"
    assert "p@ss" not in str(engine.url) and "p@ss" not in repr(_config())


@pytest.mark.parametrize(
    "mudanca",
    [{"host": ""}, {"usuario": ""}, {"database": ""}, {"porta": 0}, {"porta": 70000}, {"tamanho_pool": 0},
     {"tamanho_pool": 99}, {"timeout_conexao": 0}, {"timeout_pool": -1}],
)
def test_rejeita_configuracao_invalida(mudanca):
    with pytest.raises(ValueError):
        _config(**mudanca)
