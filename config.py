import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USUARIO = os.getenv("MYSQL_USUARIO")
MYSQL_SENHA = os.getenv("MYSQL_SENHA")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# Chave secreta do HMAC do RA (ver Aluno.gerar_hash_ra). Trocar a chave invalida todos os hashes salvos.
RA_SALT = os.getenv("RA_SALT")

# RAG: modelos do Hugging Face rodando localmente. Trocar o modelo de embedding
# exige reindexar os PDFs (os vetores antigos deixam de servir).
MODELO_EMBEDDING = os.getenv(
    "MODELO_EMBEDDING", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MODELO_GERADOR = os.getenv("MODELO_GERADOR", "Qwen/Qwen2.5-1.5B-Instruct")
