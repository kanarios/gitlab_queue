"""Test that calling initialize() twice raises RuntimeError."""

from __future__ import annotations

import vedro
from vedro import catched

from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.db.database import DatabaseAlreadyInitializedError


class Scenario(vedro.Scenario):
    subject = "calling initialize() twice raises DatabaseAlreadyInitializedError"

    async def given_already_initialized_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_initialize_is_called_again(self):
        with catched(DatabaseAlreadyInitializedError) as self.exc_info:
            await self.db.initialize()

    def then_database_already_initialized_error_is_raised(self):
        assert self.exc_info.type is DatabaseAlreadyInitializedError

    def and_error_message_mentions_already_initialized(self):
        assert "already initialized" in str(self.exc_info.value).lower()

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
