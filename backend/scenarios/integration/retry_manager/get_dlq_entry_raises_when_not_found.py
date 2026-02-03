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
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        self.manager = create_test_retry_manager(self.db)
        await self.manager.ensure_schema()

    async def when_non_existent_dlq_entry_is_fetched(self):
        with catched(DLQItemNotFoundError) as self.exc_info:
            await self.manager.get_dlq_entry(999)

    def then_error_should_indicate_item_not_found(self):
        assert self.exc_info.value.item_id == 999
        assert "999" in str(self.exc_info.value)

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
