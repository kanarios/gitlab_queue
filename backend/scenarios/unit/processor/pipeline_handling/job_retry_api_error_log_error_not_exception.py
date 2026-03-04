"""Test that job retry API error uses log.warning instead of log.exception.

When retry_pipeline_job raises GitLabAPIError, the processor should call
log.warning (not log.exception) because the exception is already captured in the
result and log.exception outside an except-block loses the traceback anyway.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry API error uses log.warning not log.exception"

    def given_processor_with_failing_retry_job(self):
        self.processor = create_mock_processor()
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.failed_job = MagicMock()
        self.failed_job.id = 10
        self.failed_job.name = "unit_tests"
        self.failed_job.status = "failed"

        self.processor.gitlab_client.retry_pipeline_job = AsyncMock(side_effect=GitLabAPIError("Retry failed"))

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.retried_jobs: dict[str, int] = {}

    async def when_dispatch_job_retries_is_called(self):
        with patch("gitlab_queue.core.pipeline_handler.log") as self.log_mock:
            # Pass arguments positionally so the test survives the jobs_still_failed → jobs_to_retry rename
            await self.processor._pipeline_handler.dispatch_job_retries(
                self.ctx,
                self.pipeline,
                [self.failed_job],
                self.retried_jobs,
                1,
            )

    def then_log_exception_was_not_called(self):
        self.log_mock.exception.assert_not_called()

    def and_log_warning_was_called(self):
        self.log_mock.warning.assert_called_once()
