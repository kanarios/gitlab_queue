"""Test scenarios for QueueManager FIFO ordering.

Tests that MRs are processed in first-in-first-out order,
including ordering by queued_at, get_next behavior, active queue
ordering, and position calculations.
"""

import asyncio

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


class Scenario__mrs_ordered_by_queued_at(vedro.Scenario):
    subject = "MRs are ordered by queued_at timestamp"

    async def given_queue_with_mrs_added_in_sequence(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs with delays to ensure distinct timestamps
        self.iid_order = [10, 20, 30]
        for iid in self.iid_order:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)

    async def when_active_queue_is_retrieved(self):
        self.active_queue = await self.queue.get_active_queue()

    def then_order_should_match_insertion_order(self):
        actual_order = [item.mr_iid for item in self.active_queue]
        assert actual_order == self.iid_order, f"Expected {self.iid_order}, got {actual_order}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__get_next_returns_oldest_mr(vedro.Scenario):
    subject = "get_next_mr returns oldest queued MR"

    async def given_queue_with_multiple_mrs(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs in specific order
        for iid in [100, 200, 300]:
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)

    async def when_next_mr_is_requested(self):
        self.next_item = await self.queue.get_next_mr()

    def then_oldest_mr_should_be_returned(self):
        assert self.next_item is not None
        assert (
            self.next_item.mr_iid == 100
        ), f"Expected oldest MR (100), got {self.next_item.mr_iid}"

    async def and_subsequent_calls_return_same_until_state_change(self):
        # get_next_mr returns status='queued' only, so calling again returns same
        second_next = await self.queue.get_next_mr()
        assert second_next is not None
        assert second_next.mr_iid == 100

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__get_active_queue_returns_fifo_order(vedro.Scenario):
    subject = "get_active_queue returns MRs in FIFO order"

    async def given_queue_with_mrs_in_various_states(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add 5 MRs
        for iid in [1, 2, 3, 4, 5]:
            mr = create_test_mr(iid=iid)
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)
        # Change some states (but they remain in active queue)
        await self.queue.update_mr_state(2, "rebasing")
        await self.queue.update_mr_state(4, "testing")

    async def when_active_queue_is_retrieved(self):
        self.active_queue = await self.queue.get_active_queue()

    def then_all_active_mrs_should_be_in_fifo_order(self):
        actual_order = [item.mr_iid for item in self.active_queue]
        expected_order = [1, 2, 3, 4, 5]
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    def and_queue_should_have_5_items(self):
        assert len(self.active_queue) == 5

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__position_reflects_fifo_order(vedro.Scenario):
    subject = "position calculation reflects FIFO order"

    async def given_queue_with_three_mrs(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add MRs in order: 5, 15, 25
        for iid in [5, 15, 25]:
            mr = create_test_mr(iid=iid)
            await self.queue.add_to_queue(mr)
            await asyncio.sleep(0.01)

    async def when_positions_are_queried(self):
        self.positions = {}
        for iid in [5, 15, 25]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_positions_should_reflect_insertion_order(self):
        assert self.positions[5] == 1, f"First MR expected at 1, got {self.positions[5]}"
        assert self.positions[15] == 2, f"Second MR expected at 2, got {self.positions[15]}"
        assert self.positions[25] == 3, f"Third MR expected at 3, got {self.positions[25]}"

    async def and_removing_first_should_shift_positions(self):
        await self.queue.remove_from_queue(5)
        pos_15 = await self.queue.get_queue_position(15)
        pos_25 = await self.queue.get_queue_position(25)
        assert pos_15 == 1, f"After removal, MR 15 expected at 1, got {pos_15}"
        assert pos_25 == 2, f"After removal, MR 25 expected at 2, got {pos_25}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
