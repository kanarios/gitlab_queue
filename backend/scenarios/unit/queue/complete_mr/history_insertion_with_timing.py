"""Test scenario: complete_mr inserts history record with timing metrics."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text

from gitlab_queue.core.queue import QueueManager

from ._helpers import create_test_mr

_SELECT_HISTORY_TIMING_SQL = """
SELECT wait_time_seconds, processing_time_seconds
FROM merge_requests_history WHERE iid = :iid
"""


class Scenario(vedro.Scenario):
    subject = "complete mr inserts history record with wait and processing time"

    async def given_queue_with_mr_that_started_processing(self):
        """
        Set up a test queue with a merge request (iid=42) that has begun processing.
        
        Initializes a test database and QueueManager, ensures the schema exists, creates and enqueues a test merge request with iid 42, and advances its state through "rebasing" to "testing" so the MR has a started_at timestamp.
        """
        self._db_context = initialized_test_database()
        self.db = await self._db_context.__aenter__()
        self.queue = QueueManager(db=self.db)
        await self.queue.ensure_schema()

        mr = create_test_mr(iid=42)
        await self.queue.add_to_queue(mr)
        # Transition through rebasing to testing (sets started_at)
        await self.queue.update_mr_state(42, "rebasing")
        await self.queue.update_mr_state(42, "testing")

    async def when_mr_is_completed(self):
        """
        Complete the merge request with iid 42 using state "merged" and record the outcome.
        
        Stores the boolean result of the completion operation in `self.result`.
        """
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        """
        Validate that the stored MR completion result indicates success.
        
        Raises:
            AssertionError: If the stored result is not True.
        """
        assert self.result is True

    async def and_history_should_have_wait_time(self):
        """
        Verify that the stored history record for iid 42 contains a wait_time_seconds field and that it is an integer.
        
        Queries the test database for the merge request history row with iid 42, stores the resulting mapping in self.history, and asserts that `wait_time_seconds` exists and is an int.
        """
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_HISTORY_TIMING_SQL),
                {"iid": 42},
            )
            self.history = result.mappings().one_or_none()
            await session.commit()

        assert self.history is not None
        assert self.history["wait_time_seconds"] is not None
        assert isinstance(self.history["wait_time_seconds"], int)

    def and_history_should_have_processing_time(self):
        """
        Assert that the retrieved history record contains a processing time in seconds as an integer.
        
        Raises:
        	AssertionError: If `processing_time_seconds` is missing or is not an `int`.
        """
        assert self.history["processing_time_seconds"] is not None
        assert isinstance(self.history["processing_time_seconds"], int)

    def and_wait_time_should_be_non_negative(self):
        """
        Assert that the recorded wait time for the historical record is greater than or equal to zero.
        
        Raises:
        	AssertionError: If `wait_time_seconds` is negative or missing.
        """
        assert self.history["wait_time_seconds"] >= 0

    def and_processing_time_should_be_non_negative(self):
        """
        Assert that the recorded processing time is greater than or equal to zero.
        
        Raises:
            AssertionError: If `processing_time_seconds` is negative.
        """
        assert self.history["processing_time_seconds"] >= 0

    async def do_cleanup(self):
        """
        Tear down the test database context created for the scenario.
        
        Exits the asynchronous database context manager to release and clean up test DB resources.
        """
        await self._db_context.__aexit__(None, None, None)
