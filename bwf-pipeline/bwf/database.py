from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bwf.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # vérifie la connexion avant chaque utilisation
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """Context manager pour une session DB."""
    return SessionLocal()