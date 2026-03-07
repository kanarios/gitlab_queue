"""Test that sleep is called after RetrySignal.

When pipeline fails and a job retry is triggered (RetrySignal returned),
the handler MUST sleep before the next poll. Without sleep, the next
iteration immediately sees the still-failed pipeline (GitLab hasn't
transitioned it to 'running' yet) and exhausts the retry count.
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


class Scenario(vedro.Scenario):
    subject = "_interruptible_sleep is called after RetrySignal to avoid race condition"

    def given_handler_with_failed_then_success_pipeline(self):
        failed_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")
        success_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="success")

        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_sequence = [failed_pipeline, success_pipeline]
        # One failed job to trigger retry
        gitlab_client.pipeline_jobs_response = [create_job(id=1, name="unit_tests", status="failed")]

        queue_manager = FakeQueueManager()
        queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing", retried_jobs={}))

        self.sleep_call_count = 0

        async def fake_rebase(*args, **kwargs):
            return RebaseCheckOutcome(context=None, result=None, last_check=datetime.now(UTC), should_reset=False)

        async def fake_sleep(seconds):
            self.sleep_call_count += 1
            return True

        self.handler = create_test_pipeline_handler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=create_mock_settings(job_retry_count=1),
            rebase_check_fn=fake_rebase,
            sleep_fn=fake_sleep,
        )

        self.ctx = create_processing_context(mr_iid=42, state_machine=create_mock_state_machine())

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_sleep_was_called_after_retry_signal(self):
        assert self.sleep_call_count >= 1, (
            f"Expected sleep to be called after RetrySignal but call_count={self.sleep_call_count}"
        )

    def and_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS
