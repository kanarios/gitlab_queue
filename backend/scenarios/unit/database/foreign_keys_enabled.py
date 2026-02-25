"""Test that PRAGMA foreign_keys=ON is set during database initialization."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "foreign keys are enabled during database initialization"

    async def given_initialized_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_health_check_is_performed(self):
        self.status = await self.db.health_check()

    def then_foreign_keys_should_be_enabled(self):
        assert self.status.foreign_keys_enabled is True

    def and_database_should_be_connected(self):
        assert self.status.connected is True

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
