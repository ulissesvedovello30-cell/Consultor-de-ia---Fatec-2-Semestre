import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USUARIO = os.getenv("MYSQL_USUARIO")
MYSQL_SENHA = os.getenv("MYSQL_SENHA")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

RA_SALT = os.getenv("RA_SALT")
