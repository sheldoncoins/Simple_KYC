"""Alembic environment.

The database URL is taken from ``KYC_DATABASE_URL`` (the same variable the app
uses) so migrations and the running service always target the same database.
``target_metadata`` points at the app's models, so ``--autogenerate`` sees the
full schema.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.db import Base

# Importing the models registers every table on Base.metadata.
import app.models  # noqa: F401  (side-effect import)

config = context.config

# Let the environment win over the static alembic.ini value.
_url = os.environ.get("KYC_DATABASE_URL")
if _url:
    config.set_main_option("sqlalchemy.url", _url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _is_sqlite(url: str | None) -> bool:
    return bool(url) and url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Batch mode lets future ALTERs work under SQLite's limited DDL.
        render_as_batch=_is_sqlite(url),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(connection.engine.url.render_as_string()),
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
