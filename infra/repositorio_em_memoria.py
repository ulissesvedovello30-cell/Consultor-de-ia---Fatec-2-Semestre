"""Repositório transitório apenas para demonstração e testes."""
from datetime import date
from dataclasses import replace
import uuid
import numpy as np
from dominio.metadados import Metadados
from infra.repositorio_trechos import identidade


class RepositorioEmMemoria:
    def __init__(self):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self._arquivos = {}

    def indexado(self, hash_arquivo, modelo_embedding, nome=None):
        """Verifique se a versão ativa corresponde a conteúdo, modelo e nome informados."""
        itens = self._arquivos.values()
        return any(h == hash_arquivo and m == modelo_embedding and (nome is None or ts[0].arquivo == nome)
                   for h, m, ts, vs in itens)

    def substituir_arquivo(self, hash_arquivo, modelo_embedding, trechos, embeddings, metadados=None):
        """Substitua o documento no repositório isolado de demonstração.
        
        Args:
            hash_arquivo: SHA-256 do conteúdo documental.
            modelo_embedding: Identidade do modelo e configuração dos vetores.
            trechos: Sequência de trechos públicos a persistir ou consultar.
            embeddings: Matriz de vetores alinhada à sequência de trechos.
            metadados: Metadados públicos opcionais de curso, período e vigência.
        """
        if not trechos or len(trechos) != len(embeddings):
            raise ValueError('Cada trecho precisa de exatamente um vetor.')
        documento_id, versao = identidade(trechos[0].arquivo), uuid.uuid4().hex
        meta = (metadados or Metadados()).valores()
        copia = [replace(t, documento_id=documento_id, versao_id=versao, **meta) for t in trechos]
        self._arquivos[documento_id] = (hash_arquivo, modelo_embedding, copia, embeddings)

    def carregar(self, modelo_embedding):
        """Carregue ou retorne o snapshot de trechos e vetores compatíveis com o modelo."""
        hoje = date.today()
        itens = [(ts, vs) for h, m, ts, vs in self._arquivos.values() if m == modelo_embedding]
        itens = [(ts, vs) for ts, vs in itens if (not ts[0].inicio or ts[0].inicio <= hoje)
                 and (not ts[0].fim or ts[0].fim >= hoje)]
        if not itens:
            return [], np.empty((0, 0), dtype=np.float32)
        return [t for ts, vs in itens for t in ts], np.vstack([vs for ts, vs in itens])
