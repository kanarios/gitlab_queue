"""Test that ensure_schema creates tables and is idempotent."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_payload, create_test_retry_manager


class Scenario(vedro.Scenario):
    subject = "ensure schema creates retry and dlq tables"

    async def given_retry_manager(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db)

    async def when_ensure_schema_is_called(self):
        await self.manager.ensure_schema()

    async def then_tables_should_exist(self):
        payload = create_test_payload()
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=payload,
            error="test error",
        )
        assert retry_id > 0, f"Expected retry_id > 0, got {retry_id}"

    async def and_ensure_schema_should_be_idempotent(self):
        await self.manager.ensure_schema()
        retry_id = await self.manager.add_to_retry_queue(
            event_type="merge_request",
            payload=create_test_payload(),
            error="another error",
        )
        assert retry_id > 0, f"Expected retry_id > 0 after second ensure_schema, got {retry_id}"

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
