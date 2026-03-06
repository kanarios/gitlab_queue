"""Test retried_jobs is reset after rebase during testing.

When _maybe_rebase_during_testing triggers a rebase (should_reset=True),
retried_jobs should be reset to {} in _wait_for_pipeline loop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

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
        self.processor.queue_manager.get_queue_item = AsyncMock(return_value=queue_item)

        # Pipeline succeeds after the rebase (so we need 2 iterations)
        # First iteration: running pipeline -> rebase happens -> reset
        # Second iteration: success
        running_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        success_pipeline = create_mock_pipeline(pipeline_id=101, sha="def456", status="success")

        self.processor.gitlab_client.get_latest_mr_pipeline = AsyncMock(
            side_effect=[running_pipeline, success_pipeline]
        )
        self.processor.gitlab_client.get_mr = AsyncMock(
            return_value=MagicMock(state="opened", labels=["merge_queue"], sha="abc123")
        )

        new_rebase_ctx = RebaseDuringTestingContext(max_attempts=3, rebase_count=1, current_pipeline_id=101)

        # First rebase check returns reset signal
        # Second rebase check returns no-op
        handler = self.processor._pipeline_handler
        handler.should_skip_stale_pipeline = AsyncMock(return_value=False)
        handler.check_pipeline_termination_conditions = AsyncMock(return_value=None)
        handler._interruptible_sleep = AsyncMock(return_value=True)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.captured_retried_jobs: list[dict] = []
        original_handle = handler.handle_pipeline_status

        async def capture_retried_jobs(ctx, sm, pipeline, retried_jobs):
            self.captured_retried_jobs.append(dict(retried_jobs))
            return await original_handle(ctx, sm, pipeline, retried_jobs)

        handler.handle_pipeline_status = capture_retried_jobs

        self.rebase_side_effects = [
            RebaseCheckOutcome(context=new_rebase_ctx, result=None, last_check=datetime.now(UTC), should_reset=True),
            RebaseCheckOutcome(context=new_rebase_ctx, result=None, last_check=datetime.now(UTC), should_reset=False),
        ]

    async def when_wait_for_pipeline_is_called(self):
        with patch(
            "gitlab_queue.core.pipeline_handler.maybe_rebase_during_testing",
            new_callable=AsyncMock,
            side_effect=self.rebase_side_effects,
        ):
            self.result = await self.processor._wait_for_pipeline(self.ctx)

    def then_retried_jobs_was_reset_after_rebase(self):
        # After rebase, retried_jobs should be empty
        assert len(self.captured_retried_jobs) >= 1
        # The call after rebase should have empty retried_jobs
        assert self.captured_retried_jobs[-1] == {}

    def and_retried_jobs_persisted_to_db(self):
        # Verify that after rebase reset, {} was persisted to DB
        update_calls = self.processor.queue_manager.update_mr_state.await_args_list
        retried_jobs_values = [
            call.kwargs.get("retried_jobs") for call in update_calls if "retried_jobs" in (call.kwargs or {})
        ]
        assert {} in retried_jobs_values, (
            f"Expected update_mr_state called with retried_jobs={{}} after rebase, but got: {retried_jobs_values}"
        )
