"""Test scenarios for QueueManager hotfix priority handling.

Tests that hotfix MRs get priority in the queue over regular MRs,
including position calculation, get_next behavior, and ordering of
multiple hotfixes.
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


class Scenario__hotfix_gets_priority_position(vedro.Scenario):
    subject = "hotfix MR gets priority position over regular MRs"

    async def given_queue_with_regular_mrs(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add regular MRs first
        for iid in [1, 2, 3]:
            mr = create_test_mr(iid=iid, title=f"Regular MR {iid}")
            await self.queue.add_to_queue(mr, is_hotfix=False)
            await asyncio.sleep(0.01)  # Ensure distinct queued_at

    async def when_hotfix_mr_is_added(self):
        hotfix = create_test_mr(iid=99, title="Hotfix MR")
        self.hotfix_item = await self.queue.add_to_queue(hotfix, is_hotfix=True)

    async def then_hotfix_should_be_at_position_1(self):
        position = await self.queue.get_queue_position(99)
        assert position == 1, f"Expected hotfix at position 1, got {position}"

    async def and_regular_mrs_should_shift_positions(self):
        for iid in [1, 2, 3]:
            position = await self.queue.get_queue_position(iid)
            expected = iid + 1  # Shifted by 1 due to hotfix
            assert position == expected, f"MR {iid} expected at position {expected}, got {position}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__multiple_hotfixes_ordered_by_time(vedro.Scenario):
    subject = "multiple hotfixes are ordered by queued_at within hotfix group"

    async def given_queue_with_multiple_hotfixes(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add hotfixes in order
        for iid in [10, 20, 30]:
            mr = create_test_mr(iid=iid, title=f"Hotfix {iid}")
            await self.queue.add_to_queue(mr, is_hotfix=True)
            await asyncio.sleep(0.01)  # Ensure distinct queued_at

    async def when_positions_are_queried(self):
        self.positions = {}
        for iid in [10, 20, 30]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_hotfixes_should_be_in_fifo_order(self):
        assert self.positions[10] == 1, f"First hotfix expected at 1, got {self.positions[10]}"
        assert self.positions[20] == 2, f"Second hotfix expected at 2, got {self.positions[20]}"
        assert self.positions[30] == 3, f"Third hotfix expected at 3, got {self.positions[30]}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__get_next_returns_hotfix_first(vedro.Scenario):
    subject = "get_next_mr returns hotfix before regular MRs"

    async def given_queue_with_mixed_priority(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add regular MR first
        regular = create_test_mr(iid=1, title="Regular MR")
        await self.queue.add_to_queue(regular, is_hotfix=False)
        await asyncio.sleep(0.01)
        # Add hotfix second (but should be returned first)
        hotfix = create_test_mr(iid=2, title="Hotfix MR")
        await self.queue.add_to_queue(hotfix, is_hotfix=True)

    async def when_next_mr_is_requested(self):
        self.next_item = await self.queue.get_next_mr()

    def then_hotfix_should_be_returned(self):
        assert self.next_item is not None
        assert (
            self.next_item.mr_iid == 2
        ), f"Expected hotfix (iid=2), got iid={self.next_item.mr_iid}"
        assert self.next_item.is_hotfix is True

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)


class Scenario__queue_position_respects_hotfix_priority(vedro.Scenario):
    subject = "queue position calculation respects hotfix priority"

    async def given_mixed_queue(self):
        self._db_context = test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()
        # Add: regular1, hotfix1, regular2, hotfix2
        regular1 = create_test_mr(iid=1, title="Regular 1")
        await self.queue.add_to_queue(regular1, is_hotfix=False)
        await asyncio.sleep(0.01)

        hotfix1 = create_test_mr(iid=2, title="Hotfix 1")
        await self.queue.add_to_queue(hotfix1, is_hotfix=True)
        await asyncio.sleep(0.01)

        regular2 = create_test_mr(iid=3, title="Regular 2")
        await self.queue.add_to_queue(regular2, is_hotfix=False)
        await asyncio.sleep(0.01)

        hotfix2 = create_test_mr(iid=4, title="Hotfix 2")
        await self.queue.add_to_queue(hotfix2, is_hotfix=True)

    async def when_all_positions_are_queried(self):
        self.positions = {}
        for iid in [1, 2, 3, 4]:
            self.positions[iid] = await self.queue.get_queue_position(iid)

    def then_positions_should_reflect_hotfix_priority(self):
        # Expected order: hotfix1(2), hotfix2(4), regular1(1), regular2(3)
        assert self.positions[2] == 1, f"Hotfix 1 expected at 1, got {self.positions[2]}"
        assert self.positions[4] == 2, f"Hotfix 2 expected at 2, got {self.positions[4]}"
        assert self.positions[1] == 3, f"Regular 1 expected at 3, got {self.positions[1]}"
        assert self.positions[3] == 4, f"Regular 2 expected at 4, got {self.positions[3]}"

    async def and_active_queue_should_be_in_correct_order(self):
        active = await self.queue.get_active_queue()
        expected_order = [2, 4, 1, 3]  # hotfixes first, then regulars, each group FIFO
        actual_order = [item.mr_iid for item in active]
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
