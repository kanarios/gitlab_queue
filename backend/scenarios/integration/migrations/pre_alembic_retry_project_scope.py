"""A pre-Alembic database is stamped at baseline before retry tables are upgraded."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import (
    _run_upgrade,
    _stamp_legacy_database_if_needed,
    get_current_revision,
    run_migrations,
)

_ENV_KEYS = (
    "GITLAB_QUEUE_DATABASE_URL",
    "GITLAB_QUEUE_GITLAB_PROJECT_ID",
    "GITLAB_QUEUE_PROJECTS",
)


class Scenario(vedro.Scenario):
    subject = "partial pre-Alembic database recreates missing project-scoped retry tables"

    def given_pre_alembic_database_with_retry_data(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "pre_alembic.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def when_migrations_run_from_the_legacy_baseline(self):
        os.environ["GITLAB_QUEUE_DATABASE_URL"] = self._db_url
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "101"
        os.environ["GITLAB_QUEUE_PROJECTS"] = ""
        await asyncio.to_thread(_run_upgrade, self._db_url, "34c99f29b96d")

        with sqlite3.connect(self._db_path) as connection:
            connection.execute("DROP TABLE webhook_retry_queue")
            connection.execute("DROP TABLE webhook_dlq")
            connection.execute("DROP TABLE alembic_version")

        self.stamped = await _stamp_legacy_database_if_needed(self._db_url)
        self.stamped_revision = await get_current_revision(self._db_url)
        self.migrated = await run_migrations(self._db_url)

        with sqlite3.connect(self._db_path) as connection:
            self.project_columns = {
                table: "project_id" in {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                for table in ("webhook_retry_queue", "webhook_dlq")
            }

    def then_baseline_was_stamped_and_retry_tables_were_migrated(self):
        assert self.stamped is True
        assert self.stamped_revision == "34c99f29b96d"
        assert self.migrated is True
        assert self.project_columns == {"webhook_retry_queue": True, "webhook_dlq": True}

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()
