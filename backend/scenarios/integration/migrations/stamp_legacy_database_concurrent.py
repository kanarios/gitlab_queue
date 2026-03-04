"""Verify that _stamp_legacy_database_if_needed handles concurrent stamping gracefully.

When another process stamps the database between our check and our stamp attempt,
the function should detect this and not raise an exception.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import vedro

from gitlab_queue.db.migrations import _stamp_legacy_database_if_needed


class Scenario(vedro.Scenario):
    subject = "stamp legacy database handles concurrent stamp by another process"

    def given_legacy_database(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "legacy.db"
        self.database_url = f"sqlite+aiosqlite:///{self.db_path}"

    async def given_database_with_merge_requests_table(self):
        """Create a DB that mimics a legacy database (merge_requests table, no alembic_version)."""
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

    async def when_stamp_is_called_but_another_process_already_stamped(self):
        """Simulate race condition: command.stamp raises, but get_current_revision finds a revision."""
        with (
            patch(
                "gitlab_queue.db.migrations.command.stamp",
                side_effect=Exception("UNIQUE constraint failed: alembic_version.version_num"),
            ),
            patch(
                "gitlab_queue.db.migrations.get_current_revision",
                return_value="abc123",
            ),
        ):
            self.stamped = await _stamp_legacy_database_if_needed(self.database_url)

    def then_it_should_return_true(self):
        assert self.stamped is True

    def and_no_exception_was_raised(self):
        # If we got here, no exception was raised — test passes
        pass
