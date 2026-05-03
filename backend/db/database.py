"""
backend/db/database.py
──────────────────────
SQLAlchemy engine + session factory.
Uses settings from backend.config so there is a single env-var source.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import settings


DATABASE_URL = settings.DATABASE_URL

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    # Production PostgreSQL pool settings (silently ignored for SQLite)
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
