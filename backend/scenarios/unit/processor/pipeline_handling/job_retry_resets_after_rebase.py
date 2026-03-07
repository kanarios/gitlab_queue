"""Test retried_jobs is reset after rebase during testing.

When rebase_check_fn triggers a rebase (should_reset=True),
retried_jobs should be reset to {} in wait_for_pipeline loop.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
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
    subject = "retried_jobs is reset to empty dict after rebase during testing"

    def given_handler_with_rebase_causing_reset(self):
        running_pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        success_pipeline = create_mock_pipeline(pipeline_id=101, sha="def456", status="success")

        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_sequence = [running_pipeline, success_pipeline]

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing", retried_jobs={"flaky": 1}))

        new_rebase_ctx = RebaseDuringTestingContext(max_attempts=3, rebase_count=1, current_pipeline_id=101)

        rebase_outcomes = iter(
            [
                RebaseCheckOutcome(
                    context=new_rebase_ctx,
                    result=None,
                    last_check=datetime.now(UTC),
                    should_reset=True,
                ),
                RebaseCheckOutcome(
                    context=new_rebase_ctx,
                    result=None,
                    last_check=datetime.now(UTC),
                    should_reset=False,
                ),
            ]
        )

        async def fake_rebase(*args, **kwargs):
            return next(rebase_outcomes)

        async def fake_sleep(seconds):
            return True

        self.handler = create_test_pipeline_handler(
            gitlab_client=gitlab_client,
            queue_manager=self.queue_manager,
            settings=create_mock_settings(job_retry_count=1),
            rebase_check_fn=fake_rebase,
            sleep_fn=fake_sleep,
        )

        self.ctx = create_processing_context(mr_iid=42, state_machine=create_mock_state_machine())

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_retried_jobs_persisted_to_db_as_empty(self):
        retried_jobs_values = [
            call.get("retried_jobs") for call in self.queue_manager.update_state_calls if "retried_jobs" in call
        ]
        assert {} in retried_jobs_values, (
            f"Expected update_mr_state called with retried_jobs={{}} after rebase, but got: {retried_jobs_values}"
        )
