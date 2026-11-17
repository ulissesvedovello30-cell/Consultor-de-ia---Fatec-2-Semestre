"""Configuração do serviço; segredos são lidos somente no servidor."""
import os
from pathlib import Path
from dotenv import load_dotenv
from infra.gemini_http import chave_gemini, nome_modelo

load_dotenv(Path(__file__).parent / '.env')
BUSCA_ACERVO = os.getenv('BUSCA_ACERVO', 'textual').strip().lower()
PERFIL = os.getenv('CHATBOT_PERFIL', 'mvp').strip().lower()
SQLITE_CAMINHO = os.getenv('SQLITE_CAMINHO', 'runtime/acervo.sqlite3')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
MODELO_GERADOR = os.getenv('GEMINI_MODELO', '').strip() or 'gemini-3.5-flash'
MODELO_EMBEDDING = os.getenv('GEMINI_EMBEDDING', '').strip() or 'gemini-embedding-001'
RAG_LIMIAR_SIMILARIDADE = float(os.getenv('RAG_LIMIAR_SIMILARIDADE', '0.65'))
RAG_TEMPO_GERACAO = float(os.getenv('RAG_TEMPO_TOTAL', '60'))
if not 0 <= RAG_LIMIAR_SIMILARIDADE <= 1 or not 1 <= RAG_TEMPO_GERACAO <= 180:
    raise ValueError('Confira o limiar (0 a 1) e o prazo (1 a 180 segundos).')


def validar_gemini():
    """Confira a configuração local antes de abrir o banco ou o servidor.

    Raises:
        ValueError: Se o nome de um modelo for inválido ou faltar a chave.
    """
    nome_modelo(MODELO_GERADOR, 'GEMINI_MODELO')
    if BUSCA_ACERVO not in ('textual', 'gemini'):
        raise ValueError('BUSCA_ACERVO deve ser textual ou gemini.')
    if BUSCA_ACERVO == 'gemini':
        nome_modelo(MODELO_EMBEDDING, 'GEMINI_EMBEDDING')
    chave_gemini(GEMINI_API_KEY)
