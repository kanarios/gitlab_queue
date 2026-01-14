"""Test scenarios for QueueManager.add_to_queue() method.

Tests adding MRs to the queue including empty queue, non-empty queue,
duplicate handling (idempotency), and hotfix flag setting.
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


class Scenario__add_mr_to_empty_queue(vedro.Scenario):
    subject = "add MR to empty queue"

    async def given_empty_queue(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_mr_is_added(self):
        self.mr = create_test_mr(iid=42)
        self.item = await self.queue.add_to_queue(self.mr)

    async def then_item_should_be_at_position_1(self):
        position = await self.queue.get_queue_position(42)
        assert position == 1, f"Expected position 1, got {position}"

    def and_state_should_be_queued(self):
        assert self.item.state == "queued", f"Expected 'queued', got {self.item.state}"

    def and_mr_data_should_match(self):
        assert self.item.mr_iid == 42
        assert self.item.title == "Test MR"
        assert self.item.author_name == "Test User"
        assert self.item.author_username == "testuser"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__add_mr_to_non_empty_queue(vedro.Scenario):
    subject = "add MR to non-empty queue"

    async def given_queue_with_one_mr(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add first MR
        first_mr = create_test_mr(iid=1, title="First MR")
        await self.queue.add_to_queue(first_mr)

    async def when_second_mr_is_added(self):
        second_mr = create_test_mr(iid=2, title="Second MR")
        self.item = await self.queue.add_to_queue(second_mr)

    async def then_item_should_be_at_position_2(self):
        position = await self.queue.get_queue_position(2)
        assert position == 2, f"Expected position 2, got {position}"

    async def and_first_mr_should_still_be_at_position_1(self):
        position = await self.queue.get_queue_position(1)
        assert position == 1, f"Expected position 1, got {position}"

    async def and_queue_length_should_be_2(self):
        length = await self.queue.get_queue_length()
        assert length == 2, f"Expected length 2, got {length}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__add_duplicate_mr_is_idempotent(vedro.Scenario):
    subject = "add duplicate MR is idempotent"

    async def given_queue_with_existing_mr(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MR first time
        mr = create_test_mr(iid=42, title="Original Title")
        self.first_item = await self.queue.add_to_queue(mr)

    async def when_same_mr_is_added_again(self):
        # Try to add same MR with different title
        mr = create_test_mr(iid=42, title="New Title")
        self.second_item = await self.queue.add_to_queue(mr)

    def then_returned_item_should_be_the_existing_one(self):
        assert self.second_item.mr_iid == self.first_item.mr_iid
        # Title should be original (not updated)
        assert self.second_item.title == "Original Title"

    async def and_queue_should_still_have_one_item(self):
        length = await self.queue.get_queue_length()
        assert length == 1, f"Expected length 1, got {length}"

    async def and_position_should_still_be_1(self):
        position = await self.queue.get_queue_position(42)
        assert position == 1, f"Expected position 1, got {position}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__add_hotfix_mr_sets_flag(vedro.Scenario):
    subject = "add hotfix MR sets is_hotfix flag"

    async def given_empty_queue(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

    async def when_hotfix_mr_is_added(self):
        mr = create_test_mr(iid=42, title="Hotfix MR")
        self.item = await self.queue.add_to_queue(mr, is_hotfix=True)

    def then_item_should_have_hotfix_flag(self):
        assert self.item.is_hotfix is True, f"Expected is_hotfix=True, got {self.item.is_hotfix}"

    async def and_item_should_be_retrievable_with_flag(self):
        retrieved = await self.queue.get_queue_item(42)
        assert retrieved is not None
        assert retrieved.is_hotfix is True

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
