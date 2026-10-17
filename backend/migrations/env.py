"""Alembic migration environment for async SQLite.

This module configures Alembic to work with async SQLAlchemy engine
and provides both offline (SQL script generation) and online
(direct database) migration modes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager, nullcontext
from logging.config import fileConfig
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import context
from filelock import FileLock
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from gitlab_queue.config import load_settings
from gitlab_queue.db.models import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

# Alembic Config object - provides access to alembic.ini values
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy metadata for autogenerate support
target_metadata = Base.metadata

logger = logging.getLogger(__name__)
_MIGRATION_LOCK_ID = 0x4749544C414251
_ARCHIVE_TABLES = frozenset(("gq_retry_rollback_manifest_v1", "gq_retry_rollback_rows_v1", "gq_dlq_rollback_rows_v1"))


def include_name(name, type_, _parent_names):
    """Keep only the frozen rollback archive outside model autogeneration."""
    return type_ != "table" or name not in _ARCHIVE_TABLES


@contextmanager
def migration_gate(connection):
    """Raw Alembic owns the same gate as the complete startup migration cycle."""
    if config.attributes.get("_startup_migration_lock_held", False):
        yield
    elif connection.dialect.name == "sqlite":
        path = connection.engine.url.database
        if not path or path == ":memory:":
            raise RuntimeError("Concurrent-safe migrations require a file-backed SQLite database")
        lock_path = Path(path).resolve().with_suffix(Path(path).suffix + ".migration.lock")
        with FileLock(lock_path, timeout=120):
            yield
    elif connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MIGRATION_LOCK_ID})
        yield
    else:
        raise RuntimeError("Rollback archive migrations support SQLite and PostgreSQL")


def get_database_url() -> str:
    """Get database URL from environment or application config.

    Priority:
    1. GITLAB_QUEUE_DATABASE_URL environment variable (for CI/testing)
    2. Application settings via load_settings()
    3. Fallback to alembic.ini value
    """
    override_url = config.attributes.get("database_url_override")
    if override_url:
        return str(override_url)

    # Check env var directly first (for CI where full settings may not be available)
    env_url = os.environ.get("GITLAB_QUEUE_DATABASE_URL")
    if env_url:
        return env_url

    try:
        settings = load_settings()
        if settings.database_url:
            return settings.database_url
        # settings loaded but database_url is falsy - fall through to fallback
        logger.debug("Settings loaded but database_url is empty, trying alembic.ini fallback")
    except Exception as e:
        logger.debug("Could not load settings: %s", e)

    # Fallback to alembic.ini value
    fallback_url = config.get_main_option("sqlalchemy.url", "")
    if fallback_url:
        logger.debug("Using fallback URL from alembic.ini")
        return fallback_url

    raise RuntimeError(
        "No database URL found. Set GITLAB_QUEUE_DATABASE_URL env var or configure sqlalchemy.url in alembic.ini"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to the database,
    useful for reviewing migrations or applying them manually.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a connection context."""
    transaction = nullcontext() if connection.in_transaction() else connection.begin()
    with transaction, migration_gate(connection):
        if connection.dialect.name == "sqlite":
            # sqlite3 legacy transaction mode does not begin for DDL. A logical
            # SQLAlchemy transaction alone therefore cannot protect batch ALTER.
            driver = connection.connection.driver_connection
            if not driver.in_transaction:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            transactional_ddl=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    Creates an async engine and runs migrations within
    a connection context.
    """
    # Override sqlalchemy.url with application config
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Wrapper to run async migrations in sync context.
    """
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
