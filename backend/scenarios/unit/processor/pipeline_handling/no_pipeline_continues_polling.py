"""Test _wait_for_pipeline continues polling when no pipeline is found.

When get_latest_mr_pipeline returns None, the pipeline wait loop should
continue polling rather than terminating. This test uses
_check_pipeline_termination_conditions side_effect to eventually return
ERROR on the second call to stop the loop.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait for pipeline continues polling when no pipeline found"

    def given_processor_with_no_pipeline(self):
        """
        Prepare the scenario with a mock processor and processing context where no pipeline exists for the merge request.

        Configures:
        - a mock processor,
        - a mock state machine with current state id "testing",
        - a processing context with mr_iid 42 using that state machine,
        and sets the processor's GitLab client's get_latest_mr_pipeline to return None to simulate "no pipeline found".
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "testing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # No pipeline found
        self.processor.gitlab_client.get_latest_mr_pipeline = AsyncMock(return_value=None)

    async def when_wait_for_pipeline_is_called(self):
        # First call: return None (continue), second call: return ERROR (stop loop)
        """
        Invokes the processor's _wait_for_pipeline while simulating a "no pipeline found" poll followed by a termination.

        Patches _check_pipeline_termination_conditions to first yield None (continue polling) and then ProcessingResult.ERROR (stop), patches _interruptible_sleep to be awaitable, awaits _wait_for_pipeline, and stores the outcome on self.result.
        """
        with (
            patch.object(
                self.processor,
                "_check_pipeline_termination_conditions",
                new_callable=AsyncMock,
                side_effect=[None, ProcessingResult.ERROR],
            ),
            patch.object(
                self.processor,
                "_interruptible_sleep",
                new_callable=AsyncMock,
                return_value=True,
            ) as self.mock_sleep,
        ):
            self.result = await self.processor._wait_for_pipeline(self.ctx)

    def then_result_is_error(self):
        """
        Asserts that the processor's wait result indicates an error.

        Checks that `self.result` is equal to `ProcessingResult.ERROR`.
        """
        assert self.result == ProcessingResult.ERROR

    def and_interruptible_sleep_was_called(self):
        """
        Asserts that the processor's interruptible sleep was awaited exactly once.

        Raises:
            AssertionError: If the interruptible sleep was not awaited exactly one time.
        """
        self.mock_sleep.assert_awaited_once()
