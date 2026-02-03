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
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.mock_sm.current_state.id = "testing"
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # No pipeline found
        self.processor.gitlab_client.get_latest_mr_pipeline = AsyncMock(return_value=None)

    async def when_wait_for_pipeline_is_called(self):
        # First call: return None (continue), second call: return ERROR (stop loop)
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
        assert self.result == ProcessingResult.ERROR

    def and_interruptible_sleep_was_called(self):
        self.mock_sleep.assert_called()
