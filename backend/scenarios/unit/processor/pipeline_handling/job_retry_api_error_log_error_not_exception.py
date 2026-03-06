"""Test that job retry API error uses log.warning instead of log.exception.

When retry_pipeline_job raises GitLabAPIError, the processor should call
log.warning (not log.exception) because the exception is already captured in the
result and log.exception outside an except-block loses the traceback anyway.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.fakes import create_job

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

        self.failed_job = create_job(id=10, name="unit_tests", status="failed")

        self.processor.gitlab_client.retry_job_error = GitLabAPIError("Retry failed")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.retried_jobs: dict[str, int] = {}

    async def when_dispatch_job_retries_is_called(self):
        self.log_calls: dict[str, int] = {"warning": 0, "exception": 0}

        class LogCapture:
            def __init__(self, real_log):
                self._real_log = real_log

            def __getattr__(self, name):
                return getattr(self._real_log, name)

            def warning(self_, *args, **kwargs):
                self.log_calls["warning"] += 1
                return self_._real_log.warning(*args, **kwargs)

            def exception(self_, *args, **kwargs):
                self.log_calls["exception"] += 1
                return self_._real_log.exception(*args, **kwargs)

        import gitlab_queue.core.pipeline_handler as mod

        real_log = mod.log
        mod.log = LogCapture(real_log)
        try:
            await self.processor._pipeline_handler.dispatch_job_retries(
                self.ctx,
                self.pipeline,
                [self.failed_job],
                self.retried_jobs,
                1,
            )
        finally:
            mod.log = real_log

    def then_log_exception_was_not_called(self):
        assert self.log_calls["exception"] == 0

    def and_log_warning_was_called(self):
        assert self.log_calls["warning"] >= 1
