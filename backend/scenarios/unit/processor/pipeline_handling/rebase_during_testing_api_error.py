"""Test _check_and_handle_rebase_during_testing returns PIPELINE_FAILED on GitLabAPIError.

When handle_rebase_if_needed raises GitLabAPIError (e.g. API timeout or
network failure during rebase), the handler should trigger_pipeline_failed
and return ProcessingResult.PIPELINE_FAILED.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from scenarios.fakes import FakeRebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns pipeline failed on api error"

    def given_processor_with_api_error_during_rebase(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = FakeRebaseDuringTestingHandler(
            error=GitLabAPIError("API down"),
        )

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        self.result = await self.processor._check_and_handle_rebase_during_testing(
            ctx=self.ctx,
            sm=self.mock_sm,
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            pipeline=self.pipeline,
            retry_count=0,
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
