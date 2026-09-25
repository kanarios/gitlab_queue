"""Verify that a legacy DB is stamped at its detected schema baseline."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import _run_upgrade, _stamp_legacy_database_if_needed, get_current_revision


class Scenario(vedro.Scenario):
    subject = "stamp legacy database that has merge_requests but no alembic_version"

    def given_legacy_database(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "legacy.db"
        self.database_url = f"sqlite+aiosqlite:///{self.db_path}"

    async def given_database_with_merge_requests_table(self):
        """Create the exact initial schema, then remove its Alembic version marker."""
        await asyncio.to_thread(_run_upgrade, self.database_url, "34c99f29b96d")
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DROP TABLE alembic_version")

    async def when_stamp_legacy_database_is_called(self):
        self.stamped = await _stamp_legacy_database_if_needed(self.database_url)

    async def then_it_should_stamp_the_database(self):
        assert self.stamped is True

    async def then_alembic_version_table_should_match_the_legacy_schema(self):
        revision = await get_current_revision(self.database_url)
        assert revision == "34c99f29b96d"
