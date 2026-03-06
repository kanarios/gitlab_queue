"""Test retried_jobs is reset after rebase during testing.

When _maybe_rebase_during_testing triggers a rebase (should_reset=True),
retried_jobs should be reset to {} in _wait_for_pipeline loop.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

import gitlab_queue.core.pipeline_handler as _ph_mod
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from gitlab_queue.core.types import RebaseCheckOutcome

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "retried_jobs is reset to empty dict after rebase during testing"

    def given_processor_with_rebase_causing_reset(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        # Queue item has prior retried_jobs
        queue_item = create_test_queue_item(mr_iid=42, state="testing", retried_jobs={"flaky": 1})
        self.processor.queue_manager.add_item(queue_item)

        # Pipeline succeeds after the rebase (so we need 2 iterations)
        running_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        success_pipeline = create_mock_pipeline(pipeline_id=101, sha="def456", status="success")

        self.processor.gitlab_client.latest_pipeline_sequence = [running_pipeline, success_pipeline]

        new_rebase_ctx = RebaseDuringTestingContext(max_attempts=3, rebase_count=1, current_pipeline_id=101)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.captured_retried_jobs: list[dict] = []

        # First rebase check returns reset signal, second returns no-op
        self.rebase_side_effects = iter(
            [
                RebaseCheckOutcome(
                    context=new_rebase_ctx, result=None, last_check=datetime.now(UTC), should_reset=True
                ),
                RebaseCheckOutcome(
                    context=new_rebase_ctx, result=None, last_check=datetime.now(UTC), should_reset=False
                ),
            ]
        )

    async def when_wait_for_pipeline_is_called(self):
        handler = self.processor._pipeline_handler

        async def fake_termination(*args, **kwargs):
            return None

        async def fake_skip(*args, **kwargs):
            return False

        async def fake_sleep(seconds):
            return True

        handler.check_pipeline_termination_conditions = fake_termination
        handler.should_skip_stale_pipeline = fake_skip
        handler._interruptible_sleep = fake_sleep

        original_handle = handler.handle_pipeline_status

        async def capture_retried_jobs(ctx, sm, pipeline, retried_jobs):
            self.captured_retried_jobs.append(dict(retried_jobs))
            return await original_handle(ctx, sm, pipeline, retried_jobs)

        handler.handle_pipeline_status = capture_retried_jobs

        async def fake_rebase(*args, **kwargs):
            return next(self.rebase_side_effects)

        original = _ph_mod.maybe_rebase_during_testing
        _ph_mod.maybe_rebase_during_testing = fake_rebase
        try:
            self.result = await self.processor._wait_for_pipeline(self.ctx)
        finally:
            _ph_mod.maybe_rebase_during_testing = original

    def then_retried_jobs_was_reset_after_rebase(self):
        # After rebase, retried_jobs should be empty
        assert len(self.captured_retried_jobs) >= 1
        # The call after rebase should have empty retried_jobs
        assert self.captured_retried_jobs[-1] == {}

    def and_retried_jobs_persisted_to_db(self):
        # Verify that after rebase reset, {} was persisted to DB
        retried_jobs_values = [
            call.get("retried_jobs")
            for call in self.processor.queue_manager.update_state_calls
            if "retried_jobs" in call
        ]
        assert {} in retried_jobs_values, (
            f"Expected update_mr_state called with retried_jobs={{}} after rebase, but got: {retried_jobs_values}"
        )
