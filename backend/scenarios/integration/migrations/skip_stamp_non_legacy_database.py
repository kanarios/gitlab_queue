"""Verify that _stamp_legacy_database_if_needed skips databases that already have alembic_version."""

from __future__ import annotations

import tempfile
from pathlib import Path

import aiosqlite
import vedro

from gitlab_queue.db.migrations import _stamp_legacy_database_if_needed


class Scenario(vedro.Scenario):
    subject = "skip stamping for database that already has alembic_version"

    def given_database_with_alembic_version(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "modern.db"
        self.database_url = f"sqlite+aiosqlite:///{self.db_path}"

    async def given_database_with_both_tables(self):
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                CREATE TABLE merge_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    iid INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'queued',
                    target_branch TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_username TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
                """
            )
            await db.execute("INSERT INTO alembic_version (version_num) VALUES ('some_revision')")
            await db.commit()

    async def when_stamp_legacy_database_is_called(self):
        self.stamped = await _stamp_legacy_database_if_needed(self.database_url)

    def then_it_should_not_stamp(self):
        assert self.stamped is False
