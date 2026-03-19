"""Test handle_pipeline_status fails when no replacement for canceled pipeline.

When a pipeline is canceled and no replacement pipeline exists,
the handler should still trigger pipeline_failed as before.

Regression test: existing behavior preserved.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, create_pipeline

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)

CANCELED_PIPELINE_ID = 1000
EXPECTED_SHA = "sha_abc"


class Scenario(vedro.Scenario):
    subject = "handle_pipeline_status fails when no replacement for canceled pipeline"

    def given_queue_item_with_expected_sha(self):
        self.queue_manager = FakeQueueManager()
        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=CANCELED_PIPELINE_ID,
            expected_sha=EXPECTED_SHA,
        )
        self.queue_manager.add_item(self.queue_item)

    def given_gitlab_client_with_no_replacement(self):
        self.gitlab_client = FakeGitLabClient(
            mr_pipelines_response=[
                create_pipeline(id=CANCELED_PIPELINE_ID, sha=EXPECTED_SHA, status="canceled"),
            ],
        )

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    def given_canceled_pipeline(self):
        self.pipeline = create_mock_pipeline(
            pipeline_id=CANCELED_PIPELINE_ID,
            sha=EXPECTED_SHA,
            status="canceled",
        )

    def given_processing_context(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def then_pipeline_failed_was_called(self):
        assert len(self.sm.pipeline_failed_calls) == 1
