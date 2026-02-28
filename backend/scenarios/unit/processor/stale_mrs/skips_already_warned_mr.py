"""Test _check_stale_mrs skips already warned MR.

When an MR already has stale_warning_sent=True, no additional warning
should be sent and mark_stale_warning_sent should not be called again.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "check stale mrs skips already warned MR"

    def given_processor_with_already_warned_stale_mr(self):
        """
        Set up a mock processor containing a stale merge request that has already been warned.

        Creates and assigns a mock processor to self.processor, constructs a test queue item with mr_iid=42,
        state="queued" and stale_warning_sent=True (assigned to self.stale_item), and configures the
        processor's queue_manager.get_stale_mrs to return a list containing that item.
        """
        self.processor = create_mock_processor()

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=True)
        self.processor.queue_manager.get_stale_mrs.return_value = [
            self.stale_item,
        ]

    async def when_check_stale_mrs_is_called(self):
        """
        Invoke the processor's stale MR checker while patching the state-machine factory.

        Patches gitlab_queue.core.processor.create_state_machine_for_mr with an AsyncMock and assigns it to `self.mock_create_sm`, then calls `self.processor._check_stale_mrs()`.
        """
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as self.mock_create_sm:
            await self.processor._check_stale_mrs()

    def then_state_machine_is_not_created(self):
        """
        Asserts that no state machine was created for the stale merge request.

        Verifies that the patched state-machine creation callable was not awaited, ensuring no new state machine was started.
        """
        self.mock_create_sm.assert_not_awaited()

    def and_warning_flag_is_not_marked(self):
        """
        Asserts that the processor's queue manager did not mark the stale-warning flag for the stale merge request.

        This verifies that mark_stale_warning_sent was not awaited/called for the already-warned MR.
        """
        self.processor.queue_manager.mark_stale_warning_sent.assert_not_awaited()
