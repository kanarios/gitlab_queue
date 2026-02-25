"""Test that health_check returns proper status dict."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.db.database import Database, DatabaseStatus


class Scenario(vedro.Scenario):
    subject = "health check reports proper status for initialized database"

    async def given_initialized_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_health_check_is_called(self):
        self.status = await self.db.health_check()

    def then_status_should_be_database_status_instance(self):
        assert isinstance(self.status, DatabaseStatus)

    def and_connected_should_be_true(self):
        assert self.status.connected is True

    def and_foreign_keys_should_be_enabled(self):
        assert self.status.foreign_keys_enabled is True

    def and_error_should_be_none(self):
        assert self.status.error is None

    def and_database_path_should_be_present(self):
        assert self.status.database_path is not None
        assert len(self.status.database_path) > 0

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)


class Scenario2(vedro.Scenario):
    subject = "health check reports not initialized for fresh database"

    def given_uninitialized_database(self):
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")

    async def when_health_check_is_called(self):
        self.status = await self.db.health_check()

    def then_connected_should_be_false(self):
        assert self.status.connected is False

    def and_error_should_mention_not_initialized(self):
        assert self.status.error is not None
        assert "not initialized" in self.status.error.lower()

    async def do_cleanup(self):
        await self.db.close()
