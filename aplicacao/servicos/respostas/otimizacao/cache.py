"""Cache temporário de seleções validadas, isolado por versão documental."""
import hashlib
import json
import time
from collections import OrderedDict
from threading import RLock
from aplicacao.servicos.respostas.otimizacao.consulta_cache import pergunta_canonica


def chave_selecao(pergunta, trechos):
    """Vincule uma consulta às evidências exatas oferecidas ao gerador.

    Args:
        pergunta (str): Consulta original do visitante.
        trechos (list): Evidências já filtradas, na ordem do contexto.

    Returns:
        str: SHA-256 sem guardar a pergunta em claro no cache.
    """
    pergunta = pergunta_canonica(pergunta, trechos)
    evidencias = [(t.arquivo, t.versao_id, t.texto, t.curso, t.periodo, t.ano,
                   t.nome_curso, t.tipo_info, t.grupo_resposta) for t in trechos]
    corpo = json.dumps([pergunta, evidencias], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(corpo.encode()).hexdigest()


class CacheSelecoes:
    """Reutilize somente seleções respondidas e limitadas em tempo e quantidade.

    Os registros internos guardam digest, seleção JSON e vencimento.
    """

    def __init__(self, capacidade=128, validade=180, relogio=time.monotonic):
        """Defina limites e relógio do armazenamento temporário.

        Args:
            capacidade (int): Máximo de seleções guardadas.
            validade (float): Tempo de reutilização em segundos.
            relogio: Relógio monotônico substituível nos testes.
        """
        if capacidade < 1 or validade <= 0:
            raise ValueError('Os limites do cache devem ser positivos.')
        self._capacidade, self._validade, self._relogio = capacidade, validade, relogio
        self._registros, self._trava = OrderedDict(), RLock()

    def obter(self, chave):
        """Consulte uma seleção ainda válida.

        Args:
            chave (str): Digest da pergunta e das evidências atuais.

        Returns:
            str | None: JSON já validado ou ausência no cache.
        """
        with self._trava:
            self.expirar()
            try:
                _, selecao = self._registros[chave]
            except KeyError:
                return None
            self._registros.move_to_end(chave)
            return selecao

    def guardar(self, chave, selecao):
        """Armazene uma seleção que o consultor já validou contra suas fontes.

        Args:
            chave (str): Digest associado às versões documentais atuais.
            selecao (str): JSON respondido e validado pelo consultor.
        """
        with self._trava:
            self.expirar()
            self._registros[chave] = self._relogio() + self._validade, selecao
            self._registros.move_to_end(chave)
            if len(self._registros) > self._capacidade:
                self._registros.popitem(last=False)

    def expirar(self):
        """Elimine seleções vencidas na consulta ou na limpeza periódica."""
        with self._trava:
            vencidas = [c for c, (fim, _) in self._registros.items() if fim <= self._relogio()]
            for chave in vencidas:
                del self._registros[chave]
