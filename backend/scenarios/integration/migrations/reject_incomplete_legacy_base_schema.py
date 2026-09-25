"""An incomplete initial schema must not be stamped as the Alembic baseline."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import _run_upgrade, _stamp_legacy_database_if_needed, get_current_revision


class Scenario(vedro.Scenario):
    subject = "reject incomplete initial legacy schema without stamping"

    def given_initial_database_missing_a_required_column(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "incomplete_base.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_legacy_stamping_is_attempted(self):
        await asyncio.to_thread(_run_upgrade, self._db_url, "34c99f29b96d")
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("ALTER TABLE merge_requests DROP COLUMN author_avatar")
            connection.execute("DROP TABLE alembic_version")

        try:
            await _stamp_legacy_database_if_needed(self._db_url)
        except RuntimeError as error:
            self.error = str(error)
        else:
            raise AssertionError("Incomplete initial schema was stamped")
        self.revision_after_error = await get_current_revision(self._db_url)

    def then_it_should_report_the_missing_column_without_stamping(self):
        assert "author_avatar" in self.error
        assert self.revision_after_error is None

    def do_cleanup(self):
        self._tmp_dir.cleanup()
