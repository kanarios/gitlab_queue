"""A project-scoped schema must not retain global merge request uniqueness."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import _run_upgrade, _stamp_legacy_database_if_needed, get_current_revision


class Scenario(vedro.Scenario):
    subject = "reject f1 schema retaining global iid uniqueness"

    def given_f1_database_with_temporary_storage(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "global_unique.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_legacy_stamping_is_attempted(self):
        await asyncio.to_thread(_run_upgrade, self._db_url, "f1a2b3c4d5e6")
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("CREATE UNIQUE INDEX legacy_global_iid_unique ON merge_requests(iid)")
            connection.execute("DROP TABLE alembic_version")

        try:
            await _stamp_legacy_database_if_needed(self._db_url)
        except RuntimeError as error:
            self.error = str(error)
        else:
            raise AssertionError("f1 schema with global iid uniqueness was stamped")
        self.revision_after_error = await get_current_revision(self._db_url)

    def then_it_should_report_global_uniqueness_without_stamping(self):
        assert "merge_requests UNIQUE(iid)" in self.error
        assert self.revision_after_error is None

    def do_cleanup(self):
        self._tmp_dir.cleanup()
