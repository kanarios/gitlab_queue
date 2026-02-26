"""Test _check_pipeline_termination_conditions triggers timeout when elapsed time exceeds limit.

When pipeline wait time exceeds the configured timeout, the processor should
trigger the timeout transition on the state machine and return TIMEOUT result.

Covers lines 804-809 in _check_pipeline_termination_conditions: elapsed > timeout
branch that calls trigger_timeout and returns ProcessingResult.TIMEOUT.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "check pipeline termination conditions triggers timeout when elapsed exceeds limit"

    def given_processor_with_elapsed_pipeline_timeout(self):
        """
        Prepare a processor, mock state machine, and processing context with a start time that exceeds the configured timeout.

        Sets:
        - self.processor: a mock processor
        - self.mock_sm: a mock state machine
        - self.ctx: a processing context for mr_iid=42 using the mock state machine
        - self.timeout: a 1-hour timeout
        - self.start_time: the current UTC time minus 2 hours so elapsed time > timeout
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # timeout is 1 hour; set start_time far enough in the past to exceed it
        self.timeout = timedelta(hours=1)
        self.start_time = datetime.now(UTC) - timedelta(hours=2)

    async def when_check_pipeline_termination_conditions_is_called(self):
        """
        Calls the processor's _check_pipeline_termination_conditions with the prepared context, state machine, timeout, and start_time, and stores the resulting ProcessingResult on self.result.
        """
        self.result = await self.processor._check_pipeline_termination_conditions(
            ctx=self.ctx,
            sm=self.mock_sm,
            timeout=self.timeout,
            start_time=self.start_time,
        )

    def then_result_is_timeout(self):
        """
        Asserts that the stored processing result indicates a timeout.

        Raises:
            AssertionError: If `self.result` is not `ProcessingResult.TIMEOUT`.
        """
        assert self.result == ProcessingResult.TIMEOUT

    def and_timeout_is_triggered_on_state_machine(self):
        """
        Asserts that the state machine's timeout transition was awaited exactly once.

        Fails the test if the mock state machine's `trigger_timeout` coroutine was not awaited exactly one time.
        """
        self.mock_sm.trigger_timeout.assert_awaited_once()

    def and_pipeline_failed_is_not_triggered(self):
        """
        Asserts that the state machine's pipeline_failed transition was not triggered.
        """
        self.mock_sm.trigger_pipeline_failed.assert_not_awaited()
