"""Test canceled pipeline beyond grace period triggers failure.

If the pipeline stays canceled for more than 3 consecutive polls,
the grace period expires and pipeline_failed is triggered as usual.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.types import RebaseCheckOutcome
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from .._helpers import (
    create_mock_pipeline,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "canceled pipeline persists beyond grace period and triggers failure"

    def given_handler_with_persistent_canceled_pipeline(self):
        canceled_pipelines = [create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled") for _ in range(4)]

        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_sequence = canceled_pipelines

        queue_manager = FakeQueueManager()
        queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing"))

        async def fake_rebase(*args, **kwargs):
            return RebaseCheckOutcome(
                context=None,
                result=None,
                last_check=datetime.now(UTC),
                should_reset=False,
            )

        async def fake_sleep(seconds):
            return True

        self.handler = create_test_pipeline_handler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=create_mock_settings(),
            rebase_check_fn=fake_rebase,
            sleep_fn=fake_sleep,
        )

        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_pipeline_failed_was_called_with_canceled_message(self):
        assert len(self.sm.pipeline_failed_calls) == 1
        call = self.sm.pipeline_failed_calls[0]
        assert "canceled" in call["error_message"].lower()
