"""Test _check_stale_mrs swallows exception from stale warning.

When create_state_machine_for_mr raises an exception during stale MR
check, the error should be caught and logged without propagating,
allowing the processor to continue checking other stale MRs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale mrs swallows exception from stale warning"

    def given_processor_with_stale_mr_and_failing_state_machine(self):
        self.processor = create_mock_processor()

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=False)
        self.processor.queue_manager.get_stale_mrs.return_value = [
            self.stale_item,
        ]

    async def when_check_stale_mrs_is_called(self):
        self.raised = None
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
            side_effect=Exception("State machine creation failed"),
        ):
            try:
                await self.processor._check_stale_mrs()
            except Exception as exc:
                self.raised = exc

    def then_no_error_is_raised(self):
        assert self.raised is None
