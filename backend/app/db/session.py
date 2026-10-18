from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Build engine kwargs; enable SSL for non-local databases (e.g., Supabase)
engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
    "hide_parameters": True,
}

if settings.DATABASE_URL.startswith("postgresql") and "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"sslmode": "require"}

target = make_url(settings.DATABASE_URL)
if target.get_backend_name() == "postgresql" and (target.host or "").endswith(".pooler.supabase.com"):
    # Supavisor owns the pool. Warm deployment workers must not retain its
    # session clients, and transaction pooling cannot reuse prepared statements.
    engine_kwargs["poolclass"] = NullPool
    if target.drivername == "postgresql+psycopg":
        engine_kwargs.setdefault("connect_args", {"sslmode": "require"})["prepare_threshold"] = None

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine,"connect")
    def sqlite_integrity(connection,record):
        connection.execute("PRAGMA foreign_keys=ON")

from app.db.tenant_session import TenantSession
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=TenantSession)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
