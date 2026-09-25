"""Concurrent startup migration runs are serialized for a legacy SQLite database."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import _run_upgrade, get_current_revision, run_migrations

_ENV_KEYS = (
    "GITLAB_QUEUE_DATABASE_URL",
    "GITLAB_QUEUE_GITLAB_PROJECT_ID",
    "GITLAB_QUEUE_PROJECTS",
)


class Scenario(vedro.Scenario):
    subject = "concurrent legacy database migrations are serialized"

    def given_legacy_database_at_the_initial_schema(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "legacy.db"
        self._database_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def given_unversioned_queue_data(self):
        await asyncio.to_thread(_run_upgrade, self._database_url, "34c99f29b96d")
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO merge_requests (
                    iid, title, author_name, author_username, status, target_branch, queued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (42, "Concurrent migration", "Alice", "alice", "queued", "main", "2026-01-01T00:00:00Z"),
            )
            connection.execute("DROP TABLE alembic_version")

        os.environ["GITLAB_QUEUE_DATABASE_URL"] = self._database_url
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "101"
        os.environ["GITLAB_QUEUE_PROJECTS"] = ""

    async def when_two_instances_run_migrations_concurrently(self):
        self.results = await asyncio.gather(
            run_migrations(self._database_url),
            run_migrations(self._database_url),
        )

    async def then_exactly_one_instance_should_apply_migrations(self):
        assert sorted(self.results) == [False, True]
        assert await get_current_revision(self._database_url) == "c3d7f1a8b902"

    def and_queue_data_should_be_preserved_and_scoped(self):
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute("SELECT iid, title, project_id FROM merge_requests WHERE iid = 42").fetchone()
        assert row == (42, "Concurrent migration", 101)

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()
