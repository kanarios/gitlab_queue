"""Test scenario: cleanup_old_entries deletes entries with old finished_at."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


def create_test_mr(
    iid: int,
    title: str = "Test MR",
    author_name: str = "Test User",
    author_username: str = "testuser",
) -> MergeRequest:
    """Create a test MergeRequest with minimal required fields."""
    return MergeRequest(
        iid=iid,
        title=title,
        state="opened",
        labels=["feature"],
        sha=f"sha{iid}",
        source_branch=f"feature-{iid}",
        target_branch="master",
        merge_status="can_be_merged",
        author=Author(id=iid, name=author_name, username=author_username),
    )


class Scenario(vedro.Scenario):
    subject = "cleanup old entries deletes entries with old finished at"

    async def given_queue_with_old_completed_mr(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Set MR to terminal state so finished_at gets set
        await self.queue.update_mr_state(42, "merged")

        # Move finished_at to the past so cleanup finds it
        async with self.db.transaction() as session:
            await session.execute(
                text("UPDATE merge_requests SET finished_at = datetime('now', '-2 days') WHERE iid = :iid"),
                {"iid": 42},
            )

    async def when_cleanup_is_run(self):
        self.deleted_count = await self.queue.cleanup_old_entries(days=1)

    def then_should_delete_1_entry(self):
        assert self.deleted_count == 1

    async def and_mr_should_not_exist_in_active_queue(self):
        item = await self.queue.get_queue_item(42)
        assert item is None

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
