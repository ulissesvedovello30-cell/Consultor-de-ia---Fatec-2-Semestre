"""Contratos estritos da API: dados extras e coerções silenciosas são recusados."""
from pydantic import BaseModel, ConfigDict, field_validator


class ModeloEstrito(BaseModel):
    """Base de entradas JSON que não permite elevar privilégios por campos adicionais."""
    model_config = ConfigDict(extra='forbid', strict=True)

    @field_validator('*')
    @classmethod
    def texto_valido(cls, valor):
        """Recuse Unicode inválido e controles invisíveis fora de quebras e tabulação."""
        if isinstance(valor, str):
            valor.encode('utf-8')
            if any(ord(c) < 32 and c not in '\n\r\t' for c in valor):
                raise ValueError('Caracteres de controle não permitidos.')
        return valor
