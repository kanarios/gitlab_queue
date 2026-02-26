"""Test scenario: complete_mr calculates wait and processing time."""

from __future__ import annotations

import vedro

from gitlab_queue.core.queue import QueueManager
from scenarios.contexts.sqlite_client import initialized_test_database

from ._helpers import create_test_mr


class Scenario(vedro.Scenario):
    subject = "complete mr calculates wait and processing time"

    async def given_queue_with_tested_mr(self):
        """
        Prepare a test queue containing a merge request (iid=42) that has been progressed to the merged state.

        Initializes a test database context and QueueManager, ensures the queue schema exists, enqueues a test MR with iid 42, advances its state to "testing" (sets started_at) and then to "merged" (sets finished_at).
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition to testing sets started_at
        await self.queue.update_mr_state(42, "testing")
        # Transition to merged sets finished_at
        await self.queue.update_mr_state(42, "merged")

    async def when_mr_is_completed(self):
        """
        Complete merge request with iid 42 marking it as "merged" and store the completion outcome on the scenario.

        The boolean result is stored in `self.result` (`True` if completion succeeded, `False` otherwise).
        """
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        """
        Asserts that the scenario's recorded result indicates a successful completion.

        Raises:
            AssertionError: If the stored result is not True.
        """
        assert self.result is True

    async def and_history_should_have_merged_status(self):
        """
        Assert that the stored history for the test merge request (iid 42) has a status of "merged".

        Raises:
                AssertionError: If the MR state is missing or its "status" is not "merged".
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["status"] == "merged"

    async def and_history_should_have_finished_at(self):
        """
        Assert that the MR history record for IID 42 contains a non-None `finished_at` timestamp.

        Raises:
            AssertionError: If the MR state does not exist or its `finished_at` is None.
        """
        state = await self.queue.get_mr_state(42)
        assert state is not None
        assert state["finished_at"] is not None

    async def do_cleanup(self):
        """
        Exit the test database context and release its resources.

        Awaits the scenario's initialized database context __aexit__ to close connections and clean up any allocated resources.
        """
        await self._db_context.__aexit__(None, None, None)
