"""Verify that _stamp_legacy_database_if_needed stamps a legacy DB with Alembic head."""

from __future__ import annotations

import tempfile
from pathlib import Path

import aiosqlite
import vedro
from alembic.script import ScriptDirectory

from gitlab_queue.db.migrations import _get_alembic_config, _stamp_legacy_database_if_needed, get_current_revision


class Scenario(vedro.Scenario):
    subject = "stamp legacy database that has merge_requests but no alembic_version"

    def given_legacy_database(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "legacy.db"
        self.database_url = f"sqlite+aiosqlite:///{self.db_path}"

    async def given_database_with_merge_requests_table(self):
        """Create a DB that mimics what ensure_schema() produces — tables exist but no alembic_version."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                CREATE TABLE merge_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    iid INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_username TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    target_branch TEXT NOT NULL,
                    queued_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def when_stamp_legacy_database_is_called(self):
        self.stamped = await _stamp_legacy_database_if_needed(self.database_url)

    async def then_it_should_stamp_the_database(self):
        assert self.stamped is True

    async def then_alembic_version_table_should_exist_with_head(self):
        revision = await get_current_revision(self.database_url)
        config = _get_alembic_config(self.database_url)
        script = ScriptDirectory.from_config(config)
        expected_head = script.get_current_head()
        assert revision == expected_head, f"Expected {expected_head}, got {revision}"
