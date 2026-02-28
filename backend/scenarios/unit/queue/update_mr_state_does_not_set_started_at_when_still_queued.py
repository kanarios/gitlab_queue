"""BUG: update_mr_state() should not set started_at when still queued."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "update_mr_state() does not set started_at when state remains queued"

    async def given_queue_with_queued_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        self.mr = MergeRequest(
            iid=42,
            title="Test MR",
            state="opened",
            labels=["merge_queue"],
            sha="abc",
            source_branch="feature-42",
            target_branch="main",
            merge_status="can_be_merged",
            author=Author(id=1, name="Alice", username="alice"),
        )

        self.item = await self.queue.add_to_queue(self.mr)
        assert self.item.started_at is None

    async def when_update_mr_state_called_with_queued(self):
        await self.queue.update_mr_state(self.mr.iid, "queued")
        self.refetched = await self.queue.get_queue_item(self.mr.iid)

    def then_started_at_should_still_be_none(self):
        assert self.refetched is not None
        assert self.refetched.started_at is None

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
