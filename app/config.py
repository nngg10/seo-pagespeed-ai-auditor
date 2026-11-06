"""Configuración centralizada leída desde variables de entorno / archivo .env."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "auditor.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _jwt_secret() -> str:
    valor = os.getenv("JWT_SECRET", "").strip()
    if valor:
        return valor
    archivo = DATA_DIR / "jwt_secret.key"
    if not archivo.exists():
        archivo.write_text(secrets.token_hex(32))
    return archivo.read_text().strip()


JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES") or 60)

PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "").strip()
PAGESPEED_TIMEOUT = 40  # segundos; el criterio CA-3.1 exige < 45 s en total

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

HOST = os.getenv("HOST") or "127.0.0.1"
PORT = int(os.getenv("PORT") or 8000)
