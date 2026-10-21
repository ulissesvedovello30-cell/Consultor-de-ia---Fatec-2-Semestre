import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USUARIO = os.getenv("MYSQL_USUARIO")
MYSQL_SENHA = os.getenv("MYSQL_SENHA")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# RAG: modelos do Hugging Face rodando localmente. Trocar o modelo de embedding
# exige reindexar os documentos (os vetores antigos deixam de servir).
MODELO_EMBEDDING = os.getenv(
    "MODELO_EMBEDDING", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MODELO_GERADOR = os.getenv("MODELO_GERADOR", "Qwen/Qwen2.5-1.5B-Instruct")

# Trecho com similaridade abaixo disso é ignorado (0 a 1). Ponto de partida: calibre com perguntas reais.
RAG_LIMIAR_SIMILARIDADE = float(os.getenv("RAG_LIMIAR_SIMILARIDADE", "0.25"))
# Segundos que a IA local pode levar numa resposta antes de desistir.
RAG_TEMPO_GERACAO = float(os.getenv("RAG_TEMPO_GERACAO", "120"))
