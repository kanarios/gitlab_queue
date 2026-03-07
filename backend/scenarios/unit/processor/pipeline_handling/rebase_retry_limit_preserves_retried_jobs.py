"""Test _check_and_handle_rebase_during_testing preserves retried_jobs on retry limit.

When handle_rebase_if_needed raises RebaseRetryLimitExceeded, the handler
should pass the existing retried_jobs (not hardcoded {}) to trigger_pipeline_failed.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseRetryLimitExceeded,
)
from scenarios.fakes import FakeRebaseDuringTestingHandler

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase retry limit preserves existing retried_jobs in trigger_pipeline_failed"

    def given_processor_with_existing_retried_jobs(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=3, max_attempts=3)
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = FakeRebaseDuringTestingHandler(
            error=RebaseRetryLimitExceeded("MR !42: 3/3 rebase attempts exhausted")
        )

        self.existing_retried_jobs = {"flaky_test": 1}

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        state = create_pipeline_wait_state(
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            retried_jobs=self.existing_retried_jobs,
        )
        self.result = await check_and_handle_rebase_during_testing(
            gitlab_client=self.processor.gitlab_client,
            ctx=self.ctx,
            state=state,
            pipeline=self.pipeline,
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called_with_existing_retried_jobs(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["retried_jobs"] == {"flaky_test": 1}
