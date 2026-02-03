"""Test _check_pipeline_termination_conditions returns REMOVED when label removed.

When _verify_mr_in_queue returns False during pipeline wait (because the
queue label was removed from the MR), the method should trigger
mark_removed on the state machine and return ProcessingResult.REMOVED.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "pipeline termination returns removed when label removed"

    def given_processor_with_mr_removed_from_queue(self):
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Shutdown not set, time not exceeded
        self.timeout = timedelta(seconds=3600)
        self.start_time = datetime.now(UTC)

    async def when_check_pipeline_termination_conditions_is_called(self):
        with patch.object(
            self.processor,
            "_verify_mr_in_queue",
            new_callable=AsyncMock,
            return_value=False,
        ):
            self.result = await self.processor._check_pipeline_termination_conditions(
                ctx=self.ctx,
                sm=self.mock_sm,
                timeout=self.timeout,
                start_time=self.start_time,
            )

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_trigger_mark_removed_was_called(self):
        self.mock_sm.trigger_mark_removed.assert_called_once_with(reason="label_removed")
