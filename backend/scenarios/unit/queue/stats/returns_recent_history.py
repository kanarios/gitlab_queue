"""Test scenario: get_recent_history returns most recent completed MRs."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "get recent history returns most recent completed mrs"

    async def given_queue_with_completed_mrs(self):
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        # Add and complete 3 MRs to terminal states with finished_at set
        for iid in (1, 2, 3):
            mr = create_test_mr(iid=iid, title=f"MR {iid}")
            await self.queue.add_to_queue(mr)
            await self.queue.update_mr_state(iid, "merged")

    async def when_recent_history_is_retrieved(self):
        self.history = await self.queue.get_recent_history(limit=2)

    def then_should_return_2_items(self):
        assert len(self.history) == 2

    def and_items_should_be_the_most_recent(self):
        iids = {item.mr_iid for item in self.history}
        assert iids == {2, 3}

    def and_all_items_should_have_merged_status(self):
        for item in self.history:
            assert item.state == "merged"

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
