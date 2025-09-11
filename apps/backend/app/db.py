import os
from sqlalchemy import create_engine, String, Integer, Text, JSON, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.pool import NullPool
from app.settings import settings

DATABASE_URL = settings.DATABASE_URL

# Parametri pool sensati (per Postgres / MySQL). Per SQLite usiamo settaggi dedicati.
engine_kwargs: dict = {
    "future": True,
    "echo": False,
}

if DATABASE_URL.startswith("sqlite"):
    # SQLite file-based: disabilita check_same_thread e niente pool complesso
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
        "poolclass": NullPool,     # evita pool su SQLite
    })
else:
    # DB server (Postgres): abilita pool
    engine_kwargs.update({
        "pool_size": 5,            # connessioni baseline
        "max_overflow": 10,        # extra connessioni burst
        "pool_timeout": 30,        # secondi di attesa
        "pool_pre_ping": True,     # ping per evitare connessioni zombie
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_db():
    """Dependency / helper: apre e chiude la sessione in sicurezza."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    payment_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # JSON su DB “veri”; testo su SQLite
    raw: Mapped[dict | None] = mapped_column(JSON().with_variant(Text, "sqlite"), nullable=True)

    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
