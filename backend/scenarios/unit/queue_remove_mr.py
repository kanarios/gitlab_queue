"""Test scenarios for QueueManager.remove_from_queue() method.

Tests removing MRs from the queue including existing MR removal,
idempotent removal, non-existent MR handling, and position changes.
"""

import vedro
from scenarios.contexts.sqlite_client import test_database

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


class Scenario__remove_existing_mr(vedro.Scenario):
    subject = "remove existing MR from queue"

    async def given_queue_with_mr(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)

    async def when_mr_is_removed(self):
        self.result = await self.queue.remove_from_queue(42)

    def then_result_should_be_true(self):
        assert self.result is True, f"Expected True, got {self.result}"

    async def and_mr_state_should_be_removed(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "removed"

    async def and_queue_should_be_empty(self):
        length = await self.queue.get_queue_length()
        assert length == 0, f"Expected 0 active MRs, got {length}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__remove_already_removed_mr(vedro.Scenario):
    subject = "remove already removed MR is idempotent"

    async def given_queue_with_removed_mr(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Remove it once
        await self.queue.remove_from_queue(42)

    async def when_mr_is_removed_again(self):
        self.result = await self.queue.remove_from_queue(42)

    def then_result_should_be_false(self):
        assert self.result is False, f"Expected False, got {self.result}"

    async def and_mr_state_should_still_be_removed(self):
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "removed"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__remove_nonexistent_mr(vedro.Scenario):
    subject = "remove non-existent MR"

    async def given_empty_queue(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_nonexistent_mr_is_removed(self):
        self.result = await self.queue.remove_from_queue(999)

    def then_result_should_be_false(self):
        assert self.result is False, f"Expected False, got {self.result}"

    async def and_queue_should_still_be_empty(self):
        length = await self.queue.get_queue_length()
        assert length == 0, f"Expected 0, got {length}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__removed_mr_not_in_active_queue(vedro.Scenario):
    subject = "removed MR has no active queue position"

    async def given_queue_with_removed_mr(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        await self.queue.remove_from_queue(42)

    async def when_position_is_queried(self):
        self.position = await self.queue.get_queue_position(42)

    def then_position_should_be_none(self):
        assert self.position is None, f"Expected None, got {self.position}"

    async def and_active_queue_should_be_empty(self):
        active = await self.queue.get_active_queue()
        assert len(active) == 0, f"Expected empty active queue, got {len(active)} items"

    async def and_mr_should_still_exist_in_db(self):
        item = await self.queue.get_queue_item(42)
        assert item is not None, "MR should still exist in database"
        assert item.state == "removed"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
