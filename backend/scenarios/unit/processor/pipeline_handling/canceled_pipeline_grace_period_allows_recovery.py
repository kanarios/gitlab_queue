"""Test grace period allows recovery from transient canceled status.

After retry_pipeline(), GitLab temporarily returns canceled/canceling for
the same pipeline_id. The grace period (3 polls) should allow the pipeline
to transition back to running/success without triggering pipeline_failed.
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
    subject = "canceled pipeline grace period allows recovery to success"

    def given_handler_with_canceled_then_running_then_success_pipeline(self):
        canceled1 = create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled")
        canceled2 = create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled")
        running = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        success = create_mock_pipeline(pipeline_id=100, sha="abc123", status="success")

        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_sequence = [canceled1, canceled2, running, success]

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

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_pipeline_failed_was_not_called(self):
        assert self.sm.pipeline_failed_calls == []
