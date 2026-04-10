"""Alembic environment configuration for persistence schema migrations.

This script integrates with app/adapters/persistence for consistent
database URL handling (env > database_url > sqlite fallback).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# This is the Alembic Config object, which provides the values of the
# [alembic] section of the .ini file as key/value pairs to the
# config.get_section method. We can then use these for Python application logic.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Add the app root to path so we can import SQLAlchemy models
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from app.adapters.persistence.sql_store import Base

# target_metadata is used to autogenerate migrations when
# there are changes in the models
target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve database URL following app config priority:

    1. PERSISTENCE_DATABASE_URL (production override)
    2. PERSISTENCE_SQLITE_PATH (explicit sqlite file)
    3. Default sqlite in backend/sessions/persistence.sqlite3
    """
    # Check for explicit production database URL
    database_url = os.getenv("PERSISTENCE_DATABASE_URL")
    if database_url:
        return database_url

    # Check for explicit SQLite path
    sqlite_path = os.getenv("PERSISTENCE_SQLITE_PATH")
    if sqlite_path:
        db_file = Path(sqlite_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file}"

    # Default to backend/sessions/persistence.sqlite3
    default_db_path = backend_root / "sessions" / "persistence.sqlite3"
    default_db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{default_db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
