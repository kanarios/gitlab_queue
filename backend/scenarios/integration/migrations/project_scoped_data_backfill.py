"""Legacy rows are assigned only when deployment config identifies one project."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

import vedro
from vedro import catched

from gitlab_queue.db.migrations import _run_upgrade, run_migrations

_ENV_KEYS = (
    "GITLAB_QUEUE_DATABASE_URL",
    "GITLAB_QUEUE_GITLAB_PROJECT_ID",
    "GITLAB_QUEUE_PROJECTS",
)


async def _prepare_legacy_database(db_url: str, db_path: Path) -> None:
    os.environ["GITLAB_QUEUE_DATABASE_URL"] = db_url
    await asyncio.to_thread(_run_upgrade, db_url, "f1a2b3c4d5e6")

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            INSERT INTO merge_requests (
                project_id, iid, title, author_name, author_username, target_branch, queued_at
            ) VALUES (0, 42, 'Legacy MR', 'Test User', 'user', 'main', '2026-01-01T00:00:00+00:00');
            INSERT INTO merge_requests_history (
                project_id, iid, title, author_name, author_username, status, target_branch, queued_at, finished_at
            ) VALUES (0, 42, 'Legacy MR', 'Test User', 'user', 'merged', 'main',
                      '2026-01-01T00:00:00+00:00', '2026-01-01T00:05:00+00:00');
            INSERT INTO analytics_hourly (
                project_id, timestamp, queue_depth, processed_count, success_count, failed_count
            ) VALUES (0, '2026-01-01T00:00:00+00:00', 2, 1, 1, 0);
            INSERT INTO analytics_daily (
                project_id, date, total_processed, success_count, failed_count,
                conflict_count, timeout_count, hotfix_count
            ) VALUES (0, '2026-01-01', 1, 1, 0, 0, 0, 0);
            INSERT INTO webhook_retry_queue (
                event_type, payload, next_attempt_at
            ) VALUES ('merge_request', '{}', '2026-01-01T00:00:00+00:00');
            INSERT INTO webhook_dlq (
                event_type, payload, attempt_count, last_error, original_created_at
            ) VALUES ('merge_request', '{}', 3, 'failed', '2026-01-01T00:00:00+00:00');
            """
        )


class LegacySingleProjectScenario(vedro.Scenario):
    subject = "legacy project sentinel rows backfill to the configured single project"

    def given_database_at_previous_migration_revision(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "legacy_single_project.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def when_next_migration_runs_with_legacy_single_project_config(self):
        await _prepare_legacy_database(self._db_url, self._db_path)
        os.environ["GITLAB_QUEUE_PROJECTS"] = ""
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "101"
        self.result = await run_migrations(self._db_url)

        with sqlite3.connect(self._db_path) as connection:
            self.project_ids = {
                "merge_requests": connection.execute("SELECT project_id FROM merge_requests WHERE iid = 42").fetchone()[
                    0
                ],
                "merge_requests_history": connection.execute(
                    "SELECT project_id FROM merge_requests_history WHERE iid = 42"
                ).fetchone()[0],
                "analytics_hourly": connection.execute(
                    "SELECT project_id FROM analytics_hourly WHERE timestamp = '2026-01-01T00:00:00+00:00'"
                ).fetchone()[0],
                "analytics_daily": connection.execute(
                    "SELECT project_id FROM analytics_daily WHERE date = '2026-01-01'"
                ).fetchone()[0],
                "webhook_retry_queue": connection.execute(
                    "SELECT project_id FROM webhook_retry_queue WHERE id = 1"
                ).fetchone()[0],
                "webhook_dlq": connection.execute("SELECT project_id FROM webhook_dlq WHERE id = 1").fetchone()[0],
            }

    def then_legacy_merge_request_and_analytics_rows_are_backfilled(self):
        assert self.result is True
        assert self.project_ids == {
            "merge_requests": 101,
            "merge_requests_history": 101,
            "analytics_hourly": 101,
            "analytics_daily": 101,
            "webhook_retry_queue": 101,
            "webhook_dlq": 101,
        }

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()


class MultiProjectScenario(vedro.Scenario):
    subject = "multi-project migration uses the former legacy project ID as ownership hint"

    def given_database_at_previous_migration_revision(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "legacy_multi_project.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def when_next_migration_runs_with_multi_project_config(self):
        await _prepare_legacy_database(self._db_url, self._db_path)
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = "101"
        os.environ["GITLAB_QUEUE_PROJECTS"] = (
            '[{"project_id":101,"token":"secret"},{"project_id":202,"token":"secret"}]'
        )
        self.result = await run_migrations(self._db_url)

        with sqlite3.connect(self._db_path) as connection:
            self.project_ids = {
                "merge_requests": connection.execute("SELECT project_id FROM merge_requests WHERE iid = 42").fetchone()[
                    0
                ],
                "merge_requests_history": connection.execute(
                    "SELECT project_id FROM merge_requests_history WHERE iid = 42"
                ).fetchone()[0],
                "analytics_hourly": connection.execute(
                    "SELECT project_id FROM analytics_hourly WHERE timestamp = '2026-01-01T00:00:00+00:00'"
                ).fetchone()[0],
                "analytics_daily": connection.execute(
                    "SELECT project_id FROM analytics_daily WHERE date = '2026-01-01'"
                ).fetchone()[0],
                "webhook_retry_queue": connection.execute(
                    "SELECT project_id FROM webhook_retry_queue WHERE id = 1"
                ).fetchone()[0],
                "webhook_dlq": connection.execute("SELECT project_id FROM webhook_dlq WHERE id = 1").fetchone()[0],
            }

    def then_legacy_rows_are_assigned_to_the_former_single_project(self):
        assert self.result is True
        assert self.project_ids == {
            "merge_requests": 101,
            "merge_requests_history": 101,
            "analytics_hourly": 101,
            "analytics_daily": 101,
            "webhook_retry_queue": 101,
            "webhook_dlq": 101,
        }

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()


class AmbiguousMultiProjectScenario(vedro.Scenario):
    subject = "projects migration refuses to guess sentinel ownership even for one new project"

    def given_populated_legacy_database(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "ambiguous_legacy_multi_project.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def when_multi_project_migration_has_no_legacy_owner(self):
        await _prepare_legacy_database(self._db_url, self._db_path)
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = ""
        os.environ["GITLAB_QUEUE_PROJECTS"] = '[{"project_id":202,"token":"secret"}]'
        with catched(RuntimeError) as self.migration_error:
            await run_migrations(self._db_url)

    def then_migration_error_explains_how_to_resolve_ambiguous_rows(self):
        assert self.migration_error.type is RuntimeError
        assert "Cannot assign legacy project_id=0 rows when GITLAB_QUEUE_PROJECTS is set" in str(
            self.migration_error.value
        )
        assert "GITLAB_QUEUE_GITLAB_PROJECT_ID" in str(self.migration_error.value)

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()


class MissingLegacyOwnerScenario(vedro.Scenario):
    subject = "migration refuses to leave legacy project sentinel rows unassigned"

    def given_populated_legacy_database_without_project_configuration(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "missing_legacy_owner.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self._previous_environment = {key: os.environ.get(key) for key in _ENV_KEYS}

    async def when_migration_runs_without_a_resolvable_owner(self):
        await _prepare_legacy_database(self._db_url, self._db_path)
        os.environ["GITLAB_QUEUE_GITLAB_PROJECT_ID"] = ""
        os.environ["GITLAB_QUEUE_PROJECTS"] = ""
        with catched(RuntimeError) as self.migration_error:
            await run_migrations(self._db_url)

    def then_migration_error_identifies_unassigned_legacy_rows(self):
        assert self.migration_error.type is RuntimeError
        assert "project_id=0" in str(self.migration_error.value)
        assert "GITLAB_QUEUE_GITLAB_PROJECT_ID" in str(self.migration_error.value)

    def do_cleanup(self):
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp_dir.cleanup()
