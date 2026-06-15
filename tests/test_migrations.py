"""The Alembic migrations must build the full schema and reverse cleanly.

Runs against a throwaway SQLite file so CI needs no database service; because
the migration renders the models' own column types, the same script also drives
Postgres (validated via docker-compose locally).
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TABLES = {
    "users", "identities", "sessions", "ledger", "review_queue", "audit_log",
}


def _config(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _tables(db_url: str) -> set[str]:
    return set(inspect(create_engine(db_url)).get_table_names())


def test_migrations_apply_and_reverse(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setenv("KYC_DATABASE_URL", db_url)
    cfg = _config(db_url)

    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES.issubset(_tables(db_url))

    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(_tables(db_url))
