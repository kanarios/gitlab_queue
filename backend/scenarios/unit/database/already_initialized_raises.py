"""Test that calling initialize() twice raises DatabaseAlreadyInitializedError."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.db.database import DatabaseAlreadyInitializedError
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "calling initialize() twice raises DatabaseAlreadyInitializedError"

    async def given_already_initialized_database(self):
        """
        Set up an already-initialized test database and store its context for cleanup.

        This enters the initialized_test_database context, assigns the resulting database object to
        self.db, and keeps the context manager in self._db_ctx for later teardown.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_initialize_is_called_again(self):
        """
        Attempts to initialize the already-initialized database and captures the resulting DatabaseAlreadyInitializedError.

        The captured exception information is stored in self.exc_info for later assertions.
        """
        with catched(DatabaseAlreadyInitializedError) as self.exc_info:
            await self.db.initialize()

    def then_database_already_initialized_error_is_raised(self):
        """
        Verify that the captured exception type is DatabaseAlreadyInitializedError.

        Raises:
            AssertionError: If the captured exception type is not DatabaseAlreadyInitializedError.
        """
        assert self.exc_info.type is DatabaseAlreadyInitializedError

    def and_error_message_mentions_already_initialized(self):
        """
        Assert that the previously captured exception's message contains "already initialized" (case-insensitive).

        Raises:
            AssertionError: If the exception message does not contain the phrase.
        """
        assert "already initialized" in str(self.exc_info.value).lower()

    async def do_cleanup(self):
        """
        Exit the previously entered database context and perform cleanup.

        This awaits the async context manager's exit to release resources allocated during setup.
        """
        await self._db_ctx.__aexit__(None, None, None)
