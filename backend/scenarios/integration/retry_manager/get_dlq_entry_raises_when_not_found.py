"""Test that get_dlq_entry raises DLQItemNotFoundError for non-existent id."""

from __future__ import annotations

import vedro
from vedro import catched

from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.webhooks.retry_manager import DLQItemNotFoundError

from ._helpers import create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "get dlq entry raises error when not found"

    async def given_retry_manager(self):
        """
        Prepare a test retry manager backed by an initialized SQLite test database and ensure its schema.
        
        Initializes the test database context, enters it to obtain the database handle, creates a test retry manager using that handle, and ensures the manager's database schema is created. Sets the following instance attributes:
        - self._db_ctx: the test database context manager
        - self.db: the entered database handle
        - self.manager: the created retry manager
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db)
        await self.manager.ensure_schema()

    async def when_non_existent_dlq_entry_is_fetched(self):
        """
        Attempts to fetch a DLQ entry with ID 999 and captures DLQItemNotFoundError.
        
        The raised DLQItemNotFoundError is caught and stored on self.exc_info for later assertions.
        """
        with catched(DLQItemNotFoundError) as self.exc_info:
            await self.manager.get_dlq_entry(999)

    def then_error_should_indicate_item_not_found(self):
        """
        Verify the captured DLQItemNotFoundError references the missing item ID 999.
        
        Asserts that the exception's `item_id` equals 999 and that the string representation of the exception contains "999".
        """
        assert self.exc_info.value.item_id == 999
        assert "999" in str(self.exc_info.value)

    async def do_cleanup(self):
        """
        Exit the initialized test database context to perform asynchronous cleanup.
        """
        await self._db_ctx.__aexit__(None, None, None)
