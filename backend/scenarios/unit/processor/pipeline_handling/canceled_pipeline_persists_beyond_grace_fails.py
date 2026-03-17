"""Test canceled pipeline beyond grace period triggers failure.

If the pipeline stays canceled for more than 3 consecutive polls,
the grace period expires and pipeline_failed is triggered with
failed/canceled job names.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.types import RebaseCheckOutcome
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)


async def _no_rebase(*args, **kwargs):
    return RebaseCheckOutcome(
        context=None,
        result=None,
        last_check=datetime.now(UTC),
        should_reset=False,
    )


async def _instant_sleep(seconds):
    return True


class Scenario(vedro.Scenario):
    subject = "canceled pipeline persists beyond grace period and triggers failure"

    def given_gitlab_client_with_persistent_canceled_pipeline(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.latest_pipeline_sequence = [
            create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled") for _ in range(4)
        ]
        self.gitlab_client.pipeline_jobs_response = [
            create_job(id=1, name="e2e-tests 1/12", status="failed"),
            create_job(id=2, name="lint", status="success"),
        ]

    def given_queue_with_testing_mr(self):
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing"))

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=create_mock_settings(),
            rebase_check_fn=_no_rebase,
            sleep_fn=_instant_sleep,
        )

    def given_processing_context(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_error_message_mentions_canceled(self):
        call = self.sm.pipeline_failed_calls[0]
        assert "canceled" in call["error_message"].lower()

    def and_error_message_contains_job_name(self):
        call = self.sm.pipeline_failed_calls[0]
        assert "e2e-tests 1/12" in call["error_message"]
