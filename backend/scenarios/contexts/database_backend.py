"""Disposable migrated database URLs for backend-independent functional tests."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def isolated_database_url(*, sqlite_in_memory: bool = False) -> AsyncIterator[str]:
    """Use a fresh PostgreSQL database when opted in, otherwise a temporary SQLite file.

    GITLAB_QUEUE_TEST_POSTGRES_URL names a disposable PostgreSQL admin database.
    Its role needs CREATEDB. Only uniquely generated test databases are dropped.
    """
    admin_url = os.getenv("GITLAB_QUEUE_TEST_POSTGRES_URL")
    if admin_url is None:
        if sqlite_in_memory:
            yield "sqlite+aiosqlite:///:memory:"
            return
        with TemporaryDirectory() as directory:
            yield f"sqlite+aiosqlite:///{Path(directory) / 'queue.db'}"
        return

    parsed = make_url(admin_url)
    if parsed.drivername != "postgresql+asyncpg":
        raise ValueError("GITLAB_QUEUE_TEST_POSTGRES_URL must use postgresql+asyncpg")
    name = f"gq_test_{uuid4().hex}"
    engine = create_async_engine(parsed, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield parsed.set(database=name).render_as_string(hide_password=False)
        finally:
            async with engine.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()
