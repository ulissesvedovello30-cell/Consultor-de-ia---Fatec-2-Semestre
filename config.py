"""Configuração do serviço; segredos são lidos somente no servidor."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')
MYSQL_HOST = os.getenv('MYSQL_HOST', '')
MYSQL_USUARIO = os.getenv('MYSQL_USUARIO', '')
MYSQL_SENHA = os.getenv('MYSQL_SENHA', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', '')
MYSQL_PORTA = int(os.getenv('MYSQL_PORTA', '3306'))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
MODELO_GERADOR = os.getenv('GEMINI_MODELO', '')
MODELO_EMBEDDING = os.getenv('GEMINI_EMBEDDING', 'gemini-embedding-001')
RAG_LIMIAR_SIMILARIDADE = float(os.getenv('RAG_LIMIAR_SIMILARIDADE', '0.65'))
RAG_TEMPO_GERACAO = float(os.getenv('RAG_TEMPO_TOTAL', '60'))
if not 0 <= RAG_LIMIAR_SIMILARIDADE <= 1 or not 1 <= RAG_TEMPO_GERACAO <= 180:
    raise ValueError('Confira o limiar (0 a 1) e o prazo (1 a 180 segundos).')
