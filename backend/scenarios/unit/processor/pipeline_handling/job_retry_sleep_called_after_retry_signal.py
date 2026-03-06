"""Test that _interruptible_sleep is called after RetrySignal.

When pipeline fails and a job retry is triggered (RetrySignal returned),
the processor MUST sleep before the next poll. Without sleep, the next
iteration immediately sees the still-failed pipeline (GitLab hasn't
transitioned it to 'running' yet) and exhausts the retry count.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

import gitlab_queue.core.pipeline_handler as _ph_mod
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from gitlab_queue.core.types import RebaseCheckOutcome, RetrySignal

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "_interruptible_sleep is called after RetrySignal to avoid race condition"

    def given_processor_with_failed_then_success_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        queue_item = create_test_queue_item(mr_iid=42, state="testing", retried_jobs={})
        self.processor.queue_manager.add_item(queue_item)

        failed_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")
        success_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="success")
        self.processor.gitlab_client.latest_pipeline_sequence = [failed_pipeline, success_pipeline]

        self.no_op_outcome = RebaseCheckOutcome(
            context=RebaseDuringTestingContext(max_attempts=3),
            result=None,
            last_check=datetime.now(UTC),
            should_reset=False,
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.sleep_call_count = 0
        self.status_call_count = 0

    async def when_wait_for_pipeline_is_called(self):
        handler = self.processor._pipeline_handler

        async def fake_termination(*args, **kwargs):
            return None

        async def fake_skip(*args, **kwargs):
            return False

        retry_signal = RetrySignal(
            retried_jobs={"unit_tests": 1},
            new_start_time=datetime.now(UTC),
        )

        status_responses = iter([retry_signal, ProcessingResult.SUCCESS])

        async def fake_status(*args, **kwargs):
            self.status_call_count += 1
            return next(status_responses)

        async def fake_sleep(seconds):
            self.sleep_call_count += 1
            return True

        handler.check_pipeline_termination_conditions = fake_termination
        handler.should_skip_stale_pipeline = fake_skip
        handler.handle_pipeline_status = fake_status
        handler._interruptible_sleep = fake_sleep

        async def fake_rebase(*args, **kwargs):
            return self.no_op_outcome

        original = _ph_mod.maybe_rebase_during_testing
        _ph_mod.maybe_rebase_during_testing = fake_rebase
        try:
            self.result = await self.processor._wait_for_pipeline(self.ctx)
        finally:
            _ph_mod.maybe_rebase_during_testing = original

    def then_sleep_was_called_after_retry_signal(self):
        assert self.sleep_call_count >= 1, (
            f"Expected _interruptible_sleep to be called after RetrySignal but call_count={self.sleep_call_count}"
        )

    def and_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS
