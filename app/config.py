import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/controle_financeiro.db")
# SECRET_KEY é opcional e atualmente não utilizada (as sessões usam tokens
# aleatórios em memória, sem assinatura). Mantida para uso futuro e
# documentada no .env.example.
SECRET_KEY = os.getenv("SECRET_KEY", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Habilita/desabilita o login com Google OAuth. Ausente = habilitado (1),
# preservando o comportamento atual em instalações existentes.
GOOGLE_OAUTH_ENABLED = os.getenv("GOOGLE_OAUTH_ENABLED", "1").strip().lower() in (
    "1", "true", "yes", "on",
)
QUOTE_CACHE_TTL = int(os.getenv("QUOTE_CACHE_TTL", "3600"))

# SQLite não cria diretórios automaticamente: garante que o diretório do
# banco exista antes de criar o engine (cobre execução local e Docker).
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.removeprefix("sqlite:///")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
