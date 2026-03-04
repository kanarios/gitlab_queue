"""Programmatic Alembic migrations runner.

Provides functions to run database migrations at application startup,
ensuring the database schema is always up-to-date.

Example:
    >>> from gitlab_queue.db.migrations import run_migrations
    >>> await run_migrations("sqlite+aiosqlite:///data/queue.db")
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from gitlab_queue.utils.logging import get_logger

log = get_logger(__name__)


def _get_alembic_config(database_url: str) -> Config:
    """Create Alembic config with correct paths.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        Configured Alembic Config object.
    """
    # Find alembic.ini relative to this file
    # This file is at: src/gitlab_queue/db/migrations.py
    # alembic.ini is at: backend/alembic.ini
    current_dir = Path(__file__).parent
    backend_dir = current_dir.parent.parent.parent  # Go up to backend/
    alembic_ini = backend_dir / "alembic.ini"

    if not alembic_ini.exists():
        # Try alternative path (when running from different locations)
        alembic_ini = Path("alembic.ini")

    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", database_url)

    # Ensure script_location is absolute
    migrations_dir = backend_dir / "migrations"
    if migrations_dir.exists():
        config.set_main_option("script_location", str(migrations_dir))

    return config


async def get_current_revision(database_url: str) -> str | None:
    """Get current database revision.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        Current revision string or None if no migrations applied.
    """
    engine = create_async_engine(database_url, poolclass=pool.NullPool)

    try:
        async with engine.connect() as conn:
            # Check if alembic_version table exists
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            )
            if result.fetchone() is None:
                return None

            # Get current revision
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None
    finally:
        await engine.dispose()


async def get_pending_migrations(database_url: str) -> list[str]:
    """Get list of pending migration revisions.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        List of pending revision IDs.
    """
    config = _get_alembic_config(database_url)
    script = ScriptDirectory.from_config(config)

    current = await get_current_revision(database_url)
    head = script.get_current_head()

    if current == head:
        return []

    # Get all revisions between current and head
    pending = []
    for rev in script.iterate_revisions(head, current):
        if rev.revision != current:
            pending.append(rev.revision)

    return list(reversed(pending))


def _run_upgrade(database_url: str, revision: str = "head") -> None:
    """Run alembic upgrade synchronously.

    This is called in a thread pool to avoid blocking the event loop.

    Args:
        database_url: SQLAlchemy database URL.
        revision: Target revision (default: "head").
    """
    config = _get_alembic_config(database_url)
    command.upgrade(config, revision)


async def _stamp_legacy_database_if_needed(database_url: str) -> bool:
    """Stamp a legacy database with the current Alembic head revision.

    Detects databases created before Alembic was introduced: they have
    the ``merge_requests`` table but no ``alembic_version`` table.
    For such databases we run ``alembic stamp head`` so that future
    migrations start from the correct baseline.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        True if stamping was performed, False otherwise.
    """
    engine = create_async_engine(database_url, poolclass=pool.NullPool)

    try:
        async with engine.connect() as conn:
            # Check if merge_requests table exists (i.e. DB was created by ensure_schema)
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='merge_requests'")
            )
            has_merge_requests = result.fetchone() is not None

            # Check if alembic_version table exists
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            )
            has_alembic_version = result.fetchone() is not None
    finally:
        await engine.dispose()

    if has_merge_requests and not has_alembic_version:
        log.info("Legacy database detected, stamping with current head revision")
        config = _get_alembic_config(database_url)
        try:
            await asyncio.to_thread(command.stamp, config, "head")
            log.info("Legacy database stamped successfully")
        except Exception:
            current = await get_current_revision(database_url)
            if current is not None:
                log.info("Database already stamped by another process", revision=current)
            else:
                raise
        return True

    return False


async def run_migrations(database_url: str, revision: str = "head") -> bool:
    """Run all pending Alembic migrations.

    This function should be called at application startup to ensure
    the database schema is up-to-date.

    Args:
        database_url: SQLAlchemy database URL.
        revision: Target revision (default: "head" for latest).

    Returns:
        True if migrations were applied, False if already up-to-date.

    Example:
        >>> async def startup():
        ...     await run_migrations("sqlite+aiosqlite:///data/queue.db")
    """
    log.info("Checking database migrations", database_url=database_url[:50] + "...")

    # Stamp legacy databases that were created before Alembic was introduced
    await _stamp_legacy_database_if_needed(database_url)

    # Check pending migrations
    pending = await get_pending_migrations(database_url)

    if not pending:
        log.info("Database schema is up-to-date")
        return False

    log.info(
        "Applying pending migrations",
        pending_count=len(pending),
        migrations=pending,
    )

    # Run migrations in thread pool (alembic is synchronous)
    await asyncio.to_thread(_run_upgrade, database_url, revision)

    log.info("Database migrations completed successfully")
    return True


async def ensure_migrations(database_url: str) -> None:
    """Ensure all migrations are applied (alias for run_migrations).

    This is the recommended function to call at application startup.

    Args:
        database_url: SQLAlchemy database URL.
    """
    await run_migrations(database_url)
