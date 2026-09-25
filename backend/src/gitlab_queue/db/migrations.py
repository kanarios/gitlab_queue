"""Programmatic Alembic migrations runner.

Provides functions to run database migrations at application startup,
ensuring the database schema is always up-to-date.

Example:
    >>> from gitlab_queue.db.migrations import run_migrations
    >>> await run_migrations("sqlite+aiosqlite:///data/queue.db")
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from filelock import FileLock
from sqlalchemy import inspect, pool, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import Connection

log = get_logger(__name__)

_POSTGRES_MIGRATION_LOCK_ID = 0x4749544C414251
_SQLITE_MIGRATION_LOCK_TIMEOUT_SECONDS = 120


async def _drain_task[T](task: asyncio.Task[T]) -> T:
    """Wait for a critical background task despite repeated caller cancellation."""
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


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
    config.attributes["database_url_override"] = database_url

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
            has_table = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table("alembic_version"))
            if not has_table:
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
    """Stamp a legacy database at the newest revision its schema satisfies.

    Detects databases created before Alembic was introduced: they have
    the ``merge_requests`` table but no ``alembic_version`` table.
    Stamping directly at head would skip migrations added after that database
    was created. We inspect additive schema markers and stamp the matching
    baseline so all newer migrations still run.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        True if stamping was performed, False otherwise.
    """
    engine = create_async_engine(database_url, poolclass=pool.NullPool)

    try:
        async with engine.connect() as conn:
            # Check if merge_requests table exists (i.e. DB was created by ensure_schema)
            has_merge_requests = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table("merge_requests"))

            # Check if alembic_version table exists
            has_alembic_version = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table("alembic_version"))

            def detect_revision(sync_conn: Connection) -> str:
                inspector = inspect(sync_conn)
                tables = set(inspector.get_table_names())
                main_tables = (
                    "merge_requests",
                    "merge_requests_history",
                    "analytics_hourly",
                    "analytics_daily",
                )
                history_tables = set(main_tables[1:])
                present_history_tables = history_tables & tables
                missing_history_tables = history_tables - present_history_tables
                if present_history_tables and missing_history_tables:
                    raise RuntimeError(
                        "Cannot stamp legacy database: history and analytics tables must be present together; "
                        f"present: {', '.join(sorted(present_history_tables))}; "
                        f"missing: {', '.join(sorted(missing_history_tables))}."
                    )

                columns_by_table = {
                    table: {column["name"] for column in inspector.get_columns(table)}
                    for table in main_tables
                    if table in tables
                }
                base_merge_request_columns = {
                    "id",
                    "iid",
                    "title",
                    "author_name",
                    "author_username",
                    "author_avatar",
                    "status",
                    "is_hotfix",
                    "labels",
                    "target_branch",
                    "queued_at",
                    "started_at",
                    "finished_at",
                    "pipeline_id",
                    "pipeline_status",
                    "retry_count",
                    "last_error",
                    "stale_warning_sent",
                    "created_at",
                }
                missing_base_columns = base_merge_request_columns - columns_by_table["merge_requests"]
                if missing_base_columns:
                    raise RuntimeError(
                        "Cannot stamp legacy database: merge_requests does not satisfy the initial schema; "
                        f"missing columns: {', '.join(sorted(missing_base_columns))}."
                    )
                project_id_tables = {table for table, columns in columns_by_table.items() if "project_id" in columns}

                if project_id_tables:
                    missing_main_tables = set(main_tables) - tables
                    missing_project_id_tables = {
                        table
                        for table in main_tables
                        if table in tables and "project_id" not in columns_by_table[table]
                    }
                    late_columns = ("expected_sha", "retried_jobs", "processing_attempts")
                    missing_late_columns = set(late_columns) - columns_by_table["merge_requests"]
                    incomplete_parts = []
                    if missing_main_tables:
                        incomplete_parts.append(f"missing tables: {', '.join(sorted(missing_main_tables))}")
                    if missing_project_id_tables:
                        incomplete_parts.append(
                            f"missing project_id in: {', '.join(sorted(missing_project_id_tables))}"
                        )
                    if missing_late_columns:
                        incomplete_parts.append(
                            f"missing merge_requests columns: {', '.join(column for column in late_columns if column in missing_late_columns)}"
                        )
                    if incomplete_parts:
                        raise RuntimeError(
                            "Cannot stamp legacy database as f1a2b3c4d5e6: incomplete project-scoped schema; "
                            + "; ".join(incomplete_parts)
                            + "."
                        )

                    expected_unique_constraints = {
                        "merge_requests": ("uq_mr_project_iid", ("project_id", "iid")),
                        "merge_requests_history": ("uq_history_project_iid", ("project_id", "iid")),
                        "analytics_hourly": ("uq_hourly_project_timestamp", ("project_id", "timestamp")),
                        "analytics_daily": ("uq_daily_project_date", ("project_id", "date")),
                    }
                    expected_indexes = {
                        "merge_requests": "idx_mr_project_id",
                        "merge_requests_history": "idx_history_project_id",
                        "analytics_hourly": "idx_hourly_project_id",
                        "analytics_daily": "idx_daily_project_id",
                    }
                    missing_project_markers = []
                    for table, (constraint_name, constraint_columns) in expected_unique_constraints.items():
                        constraints = inspector.get_unique_constraints(table)
                        if not any(
                            constraint.get("name") == constraint_name
                            and tuple(constraint["column_names"]) == constraint_columns
                            for constraint in constraints
                        ):
                            missing_project_markers.append(
                                f"unique constraint {constraint_name}({', '.join(constraint_columns)})"
                            )

                        indexes = inspector.get_indexes(table)
                        index_name = expected_indexes[table]
                        if not any(
                            index.get("name") == index_name
                            and tuple(index["column_names"]) == ("project_id",)
                            and not index.get("unique", False)
                            for index in indexes
                        ):
                            missing_project_markers.append(f"index {index_name}(project_id)")

                    old_global_uniques = []
                    for table, column in (("merge_requests", "iid"), ("analytics_daily", "date")):
                        has_global_unique_constraint = any(
                            tuple(constraint["column_names"]) == (column,)
                            for constraint in inspector.get_unique_constraints(table)
                        )
                        has_global_unique_index = any(
                            index.get("unique", False) and tuple(index["column_names"]) == (column,)
                            for index in inspector.get_indexes(table)
                        )
                        if has_global_unique_constraint or has_global_unique_index:
                            old_global_uniques.append(f"{table} UNIQUE({column})")
                    if old_global_uniques:
                        missing_project_markers.extend(
                            f"removed old global uniqueness {unique_key}" for unique_key in old_global_uniques
                        )

                    if any(
                        index.get("name") == "idx_history_iid_unique"
                        for index in inspector.get_indexes("merge_requests_history")
                    ):
                        missing_project_markers.append("removed pre-project index idx_history_iid_unique")
                    if missing_project_markers:
                        raise RuntimeError(
                            "Cannot stamp legacy database as f1a2b3c4d5e6: incomplete project-scoped constraints/indexes; "
                            f"missing or inconsistent: {', '.join(missing_project_markers)}."
                        )
                    return "f1a2b3c4d5e6"

                merge_request_columns = columns_by_table["merge_requests"]
                has_global_iid_unique = any(
                    tuple(constraint["column_names"]) == ("iid",)
                    for constraint in inspector.get_unique_constraints("merge_requests")
                ) or any(
                    index.get("unique", False) and tuple(index["column_names"]) == ("iid",)
                    for index in inspector.get_indexes("merge_requests")
                )
                if not has_global_iid_unique:
                    raise RuntimeError(
                        "Cannot stamp legacy database: pre-project merge_requests schema requires UNIQUE(iid)."
                    )
                late_columns = ("expected_sha", "retried_jobs", "processing_attempts")
                present_late_columns = {column for column in late_columns if column in merge_request_columns}
                if present_late_columns:
                    latest_marker_index = max(late_columns.index(column) for column in present_late_columns)
                    expected_prefix = set(late_columns[: latest_marker_index + 1])
                    missing_prefix_columns = expected_prefix - present_late_columns
                    if missing_prefix_columns:
                        raise RuntimeError(
                            "Cannot stamp legacy database: merge_requests migration markers are not a monotonic prefix; "
                            f"present: {', '.join(column for column in late_columns if column in present_late_columns)}; "
                            f"missing earlier columns: {', '.join(column for column in late_columns if column in missing_prefix_columns)}."
                        )

                    if missing_history_tables:
                        raise RuntimeError(
                            "Cannot stamp legacy database: merge_requests late columns require all history and analytics "
                            f"tables; missing: {', '.join(sorted(missing_history_tables))}."
                        )

                if not present_history_tables:
                    return "34c99f29b96d"

                history_indexes = inspector.get_indexes("merge_requests_history")
                history_unique_index = next(
                    (index for index in history_indexes if index.get("name") == "idx_history_iid_unique"),
                    None,
                )
                if history_unique_index is not None and (
                    not history_unique_index.get("unique", False)
                    or tuple(history_unique_index["column_names"]) != ("iid",)
                ):
                    raise RuntimeError(
                        "Cannot stamp legacy database: idx_history_iid_unique exists with an unexpected definition; "
                        "expected a unique index on merge_requests_history(iid)."
                    )

                if present_late_columns:
                    if history_unique_index is None:
                        raise RuntimeError(
                            "Cannot stamp legacy database: merge_requests late columns require the b8c5a3f12e47 "
                            "history unique index idx_history_iid_unique."
                        )
                    return {
                        1: "d61e3097360d",
                        2: "c754365eda26",
                        3: "e9a1b2c3d4f5",
                    }[len(present_late_columns)]

                if history_unique_index is not None:
                    return "b8c5a3f12e47"
                return "a312c27ba5f7"

            legacy_revision = (
                await conn.run_sync(detect_revision) if has_merge_requests and not has_alembic_version else None
            )
    finally:
        await engine.dispose()

    if has_merge_requests and not has_alembic_version:
        assert legacy_revision is not None
        log.info("Legacy database detected, stamping schema baseline", revision=legacy_revision)
        config = _get_alembic_config(database_url)
        try:
            await asyncio.to_thread(command.stamp, config, legacy_revision)
            log.info("Legacy database stamped successfully", revision=legacy_revision)
        except Exception:
            current = await get_current_revision(database_url)
            if current is not None:
                log.info("Database already stamped by another process", revision=current)
            else:
                raise
        return True

    return False


async def _run_migrations_unlocked(database_url: str, revision: str = "head") -> bool:
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


@asynccontextmanager
async def _migration_lock(database_url: str) -> AsyncIterator[None]:
    """Serialize the full migration cycle across processes and replicas."""
    url = make_url(database_url)

    if url.get_backend_name() == "sqlite":
        database_path = url.database
        if not database_path or database_path == ":memory:":
            raise RuntimeError("Concurrent-safe migrations require a file-backed SQLite database")
        lock_path = Path(database_path).resolve().with_suffix(Path(database_path).suffix + ".migration.lock")
        lock = FileLock(
            lock_path,
            timeout=_SQLITE_MIGRATION_LOCK_TIMEOUT_SECONDS,
            thread_local=False,
        )
        acquire_task = asyncio.create_task(asyncio.to_thread(lock.acquire))
        try:
            await asyncio.shield(acquire_task)
        except asyncio.CancelledError:
            await _drain_task(acquire_task)
            release_task = asyncio.create_task(asyncio.to_thread(lock.release))
            await _drain_task(release_task)
            raise
        try:
            yield
        finally:
            release_task = asyncio.create_task(asyncio.to_thread(lock.release))
            await _drain_task(release_task)
        return

    if url.get_backend_name() == "postgresql":
        engine = create_async_engine(database_url, poolclass=pool.NullPool)
        try:
            async with engine.connect() as connection, connection.begin():
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": _POSTGRES_MIGRATION_LOCK_ID},
                )
                yield
        finally:
            await engine.dispose()
        return

    raise RuntimeError(
        f"Concurrent-safe migrations are not implemented for database backend {url.get_backend_name()!r}"
    )


async def run_migrations(database_url: str, revision: str = "head") -> bool:
    """Run pending migrations while holding a database-specific startup lock."""
    async with _migration_lock(database_url):
        migration_task = asyncio.create_task(_run_migrations_unlocked(database_url, revision))
        try:
            return await asyncio.shield(migration_task)
        except asyncio.CancelledError:
            await _drain_task(migration_task)
            raise


async def ensure_migrations(database_url: str) -> None:
    """Ensure all migrations are applied (alias for run_migrations).

    This is the recommended function to call at application startup.

    Args:
        database_url: SQLAlchemy database URL.
    """
    await run_migrations(database_url)
