from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

# Build engine kwargs; enable SSL for non-local databases (e.g., Supabase)
engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}

if settings.DATABASE_URL.startswith("postgresql") and "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"sslmode": "require"}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine,"connect")
    def sqlite_integrity(connection,record):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
