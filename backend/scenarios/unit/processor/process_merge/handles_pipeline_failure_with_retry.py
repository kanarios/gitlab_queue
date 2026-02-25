"""Test _handle_pipeline_failure when retry count is at maximum.

When a pipeline fails and retry_count >= max_retries, the processor must
trigger pipeline_failed on the state machine and signal the caller to stop
retrying (should_continue=False).

Covers _handle_pipeline_failure_retry: the exhausted-retry branch that calls
trigger_pipeline_failed and returns (False, None).
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "handle pipeline failure retry triggers pipeline failed when max retries exhausted"

    def given_processor_with_failed_pipeline_and_no_retries_left(self):
        """
        Set up a processor scenario where a pipeline has failed and no retries remain.
        
        Initializes:
        - a mock processor,
        - a failed mock pipeline (id 100, sha "abc123"),
        - a mock state machine and processing context,
        - retry_count and max_retries both set to 2 (indicating retries are exhausted),
        - failed_jobs set to ["unit_tests", "lint"].
        """
        self.processor = create_mock_processor()

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # retry_count equals max_retries -> no more retries available
        self.retry_count = 2
        self.max_retries = 2
        self.failed_jobs = ["unit_tests", "lint"]

    async def when_handle_pipeline_failure_retry_is_called(self):
        """
        Invoke the processor's pipeline-failure retry handler with the scenario's prepared inputs and store its outputs for later assertions.
        
        This step calls the processor method using the scenario's ctx, pipeline, failed_jobs, retry_count, and max_retries, then assigns the returned tuple to `self.should_continue` and `self.new_start_time` for subsequent verification.
        """
        self.should_continue, self.new_start_time = await self.processor._handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            failed_jobs=self.failed_jobs,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
        )

    def then_should_continue_is_false(self):
        """
        Asserts that the handler indicated no further retries (i.e., `should_continue` is False).
        """
        assert self.should_continue is False

    def and_new_start_time_is_none(self):
        """
        Assert that the scenario's computed `new_start_time` is None.
        
        Raises:
            AssertionError: If `self.new_start_time` is not None.
        """
        assert self.new_start_time is None

    def and_pipeline_failed_is_triggered_on_state_machine(self):
        """
        Verifies that the state machine's trigger_pipeline_failed was awaited once with the expected failed jobs and retry count.
        
        Asserts that trigger_pipeline_failed was awaited exactly one time and that its call keyword arguments include `failed_jobs` equal to the scenario's failed_jobs and `retry_count` equal to the scenario's retry_count.
        """
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.call_args.kwargs
        assert call_kwargs["failed_jobs"] == self.failed_jobs
        assert call_kwargs["retry_count"] == self.retry_count

    def and_rebase_is_not_attempted(self):
        """
        Asserts that the processor did not attempt to rebase the merge request.
        
        Verifies that the `rebase_mr` coroutine on the processor's GitLab client was not awaited.
        """
        self.processor.gitlab_client.rebase_mr.assert_not_awaited()
