"""Test wait_for_pipeline sleeps and continues when stale pipeline is detected.

When should_skip_stale_pipeline returns True, sleep and continue polling.
"""

from __future__ import annotations

import asyncio
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
    subject = "wait_for_pipeline sleeps and continues when stale pipeline is skipped"

    def given_handler_with_stale_pipeline_then_shutdown(self):
        gitlab_client = FakeGitLabClient()
        gitlab_client.latest_pipeline_response = create_mock_pipeline(pipeline_id=99, sha="old_sha", status="running")

        # Queue item with pipeline_id=999 (mismatch with pipeline.id=99) → stale
        queue_manager = FakeQueueManager()
        queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing", pipeline_id=999))

        self.sleep_call_count = 0
        self.shutdown_event = asyncio.Event()

        async def fake_rebase(*args, **kwargs):
            return RebaseCheckOutcome(context=None, result=None, last_check=datetime.now(UTC), should_reset=False)

        async def fake_sleep(seconds):
            self.sleep_call_count += 1
            self.shutdown_event.set()
            return True

        self.handler = create_test_pipeline_handler(
            gitlab_client=gitlab_client,
            queue_manager=queue_manager,
            settings=create_mock_settings(pipeline_poll_interval_seconds=0.001),
            shutdown_event=self.shutdown_event,
            rebase_check_fn=fake_rebase,
            sleep_fn=fake_sleep,
        )

        self.ctx = create_processing_context(mr_iid=42, state_machine=create_mock_state_machine())

    async def when_wait_for_pipeline_is_called(self):
        self.result = await self.handler.wait_for_pipeline(self.ctx)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def and_sleep_was_called_for_stale_skip(self):
        assert self.sleep_call_count >= 1
