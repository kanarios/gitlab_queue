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
        """
        Prepare a mock processor configured to report a single stale merge request.

        Sets self.processor to a mock processor, creates self.stale_item representing MR IID 42 in state "queued" with stale_warning_sent set to False, and makes processor.queue_manager.get_stale_mrs return a list containing that item.
        """
        self.processor = create_mock_processor()

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=False)
        self.processor.queue_manager.get_stale_mrs.return_value = [
            self.stale_item,
        ]

    async def when_check_stale_mrs_is_called(self):
        """
        Invokes the processor's stale-MR check while mocking state machine creation to raise an exception and records any exception that propagates.

        The test patches create_state_machine_for_mr to raise Exception("State machine creation failed"), calls the processor's _check_stale_mrs, and stores any raised exception on self.raised (None if no exception propagated).
        """
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

    def and_mark_stale_warning_sent_is_not_called(self):
        self.processor.queue_manager.mark_stale_warning_sent.assert_not_awaited()
