from sqlalchemy import create_engine, String, Integer, Text, JSON, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from app.settings import settings

DATABASE_URL = settings.DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

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
    raw: Mapped[dict | None] = mapped_column(JSON().with_variant(Text, "sqlite"), nullable=True)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
