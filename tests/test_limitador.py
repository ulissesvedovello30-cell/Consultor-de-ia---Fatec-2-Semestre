import pytest

from core.limitador import LimitadorTaxa


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


def test_bloqueia_ao_passar_do_limite_e_libera_depois_da_janela():
    relogio = Relogio()
    limitador = LimitadorTaxa(limite=2, janela=60, relogio=relogio)

    assert limitador.permitir("a") and limitador.permitir("a")
    assert not limitador.permitir("a")

    relogio.agora += 61
    assert limitador.permitir("a")


def test_cada_conversa_tem_o_seu_proprio_limite():
    limitador = LimitadorTaxa(limite=1, janela=60, relogio=Relogio())

    assert limitador.permitir("a")
    assert limitador.permitir("b")
    assert not limitador.permitir("a")


def test_tentativa_bloqueada_nao_estende_o_bloqueio():
    relogio = Relogio()
    limitador = LimitadorTaxa(limite=1, janela=60, relogio=relogio)
    limitador.permitir("a")

    relogio.agora += 30
    assert not limitador.permitir("a")  # bloqueada; não pode renovar a janela
    relogio.agora += 31
    assert limitador.permitir("a")


@pytest.mark.parametrize("limite, janela", [(0, 60), (1, 0), (-1, 60)])
def test_rejeita_configuracao_invalida(limite, janela):
    with pytest.raises(ValueError):
        LimitadorTaxa(limite=limite, janela=janela)
