"""Database setup.

Postgres is the production target (``postgresql+psycopg://...`` via
``KYC_DATABASE_URL``); SQLite stays the zero-config default for local runs and
the test suite. The models are vanilla SQLAlchemy 2.0, so the same code serves
both -- only the URL changes. Schema is owned by Alembic (``migrations/``) in
production; ``init_db()`` is a convenience for the SQLite/dev path.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("KYC_DATABASE_URL", "sqlite:///./kyc.db")
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # SQLite needs cross-thread access for the dev server; Postgres benefits from
    # pre-ping liveness checks that recycle connections the server has dropped.
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    pool_pre_ping=not _IS_SQLITE,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Import models so they register on Base before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
