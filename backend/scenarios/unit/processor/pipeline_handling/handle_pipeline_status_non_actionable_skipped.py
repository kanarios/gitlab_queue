"""Test handle_pipeline_status triggers pipeline_failed for non-actionable statuses.

When pipeline has "skipped" status, trigger_pipeline_failed
and return PIPELINE_FAILED.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.pipeline_handler import PipelineHandler
from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, FakeSettings

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "handle_pipeline_status returns PIPELINE_FAILED for non-actionable skipped status"

    def given_processor_with_skipped_pipeline(self):
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(create_test_queue_item(mr_iid=42, state="testing"))

        self.handler = PipelineHandler(
            gitlab_client=FakeGitLabClient(),
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            shutdown_event=asyncio.Event(),
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="skipped")

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1

    def and_error_message_mentions_skipped_status(self):
        assert "skipped" in self.mock_sm.pipeline_failed_calls[0].get("error_message", "")
