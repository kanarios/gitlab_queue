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
        self.result = await self.queue.complete_mr(42, "merged")

    def then_result_should_be_true(self):
        assert self.result is True, f"Expected True, got {self.result}"

    async def and_history_should_have_wait_time(self):
        async with self.db.session() as session:
            result = await session.execute(
                text(_SELECT_HISTORY_TIMING_SQL),
                {"iid": 42},
            )
            self.history = result.mappings().one_or_none()
            await session.commit()

        assert self.history is not None, "Expected MR in history, got None"
        assert self.history["wait_time_seconds"] is not None, "Expected wait_time_seconds to be set in history"
        assert isinstance(self.history["wait_time_seconds"], int), (
            f"Expected int, got {type(self.history['wait_time_seconds'])}"
        )

    def and_history_should_have_processing_time(self):
        assert self.history["processing_time_seconds"] is not None, (
            "Expected processing_time_seconds to be set in history"
        )
        assert isinstance(self.history["processing_time_seconds"], int), (
            f"Expected int, got {type(self.history['processing_time_seconds'])}"
        )

    def and_wait_time_should_be_non_negative(self):
        assert self.history["wait_time_seconds"] >= 0, (
            f"Expected non-negative wait_time_seconds, got {self.history['wait_time_seconds']}"
        )

    def and_processing_time_should_be_non_negative(self):
        assert self.history["processing_time_seconds"] >= 0, (
            f"Expected non-negative processing_time_seconds, got {self.history['processing_time_seconds']}"
        )

    async def do_cleanup(self):
        await self._db_context.__aexit__(None, None, None)
