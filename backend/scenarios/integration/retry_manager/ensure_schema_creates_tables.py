"""Test that ensure_schema creates tables and is idempotent."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "ensure schema creates retry and dlq tables"

    async def given_retry_manager(self):
        """
        Initialize a test database context, enter it, and create a retry manager bound to that database.
        
        Sets:
        - self._db_ctx: the test database async context manager
        - self.db: the entered database instance
        - self.manager: a retry manager connected to the test database
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db)

    async def when_ensure_schema_is_called(self):
        """
        Trigger schema creation on the test retry manager to ensure required database tables exist.
        """
        await self.manager.ensure_schema()

    async def then_tables_should_exist(self):
        """
        Verifies that the retry and DLQ tables accept inserts by adding a payload to the retry queue.
        
        Adds a test payload with event_type "merge_request" and error "test error", then asserts the returned retry_id is greater than 0 indicating successful insertion.
        """
        payload = create_test_payload()
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=payload,
            error="test error",
        )
        assert retry_id > 0, f"Expected retry_id > 0, got {retry_id}"

    async def and_ensure_schema_should_be_idempotent(self):
        """
        Verifies that calling ensure_schema a second time remains idempotent.
        
        Calls the manager's ensure_schema again, inserts a test payload into the retry queue, and asserts that the insertion returns a retry_id greater than 0.
        """
        await self.manager.ensure_schema()
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="another error",
        )
        assert retry_id > 0, f"Expected retry_id > 0 after second ensure_schema, got {retry_id}"

    async def do_cleanup(self):
        """
        Close and clean up the asynchronous test database context used by the scenario.
        
        This exits the database context manager to release connections and other resources acquired for the test.
        """
        await self._db_ctx.__aexit__(None, None, None)
