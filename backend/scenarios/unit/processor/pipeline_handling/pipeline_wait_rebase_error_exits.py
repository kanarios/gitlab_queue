"""Test wait_for_pipeline returns result when rebase_check_fn returns a result.

When outcome.result is not None, return from the loop immediately.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.types import RebaseCheckOutcome
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_pipeline exits loop when maybe_rebase_during_testing returns result"

    def given_handler_with_rebase_conflict_during_testing(self):
        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_response = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        queue_manager = FakeQueueManager()
        queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing"))

        conflict_outcome = RebaseCheckOutcome(
            context=None,
            result=ProcessingResult.CONFLICT,
            last_check=datetime.now(UTC),
            should_reset=False,
        )

        async def fake_rebase(*args, **kwargs):
            return conflict_outcome

        self.handler = create_test_pipeline_handler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            rebase_check_fn=fake_rebase,
        )

        self.ctx = create_processing_context(mr_iid=42, state_machine=create_mock_state_machine())

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT
