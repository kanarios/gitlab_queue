"""Test scenario: re-adding MR after terminal state deletes old record first."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

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
    subject = "re-adding mr after terminal state deletes old record first"

    async def given_mr_in_terminal_state(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition to a terminal state (e.g., "failed")
        await self.queue.update_mr_state(42, "failed")

    async def when_mr_is_readded_to_queue(self):
        mr = create_test_mr(iid=42, title="Reopened MR")
        self.result = await self.queue.add_to_queue(mr)

    async def then_mr_should_exist_in_queue(self):
        item = await self.queue.get_queue_item(42)
        assert item is not None, "Expected MR to be in queue after re-add"

    async def and_mr_should_be_in_queued_state(self):
        item = await self.queue.get_queue_item(42)
        assert item is not None, "Expected MR in queue"
        assert item.state == "queued", f"Expected 'queued' state after re-add, got '{item.state}'"

    async def and_mr_title_should_be_updated(self):
        item = await self.queue.get_queue_item(42)
        assert item is not None, "Expected MR in queue"
        assert item.title == "Reopened MR", f"Expected 'Reopened MR', got '{item.title}'"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
