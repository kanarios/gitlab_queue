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
        self.processor = create_mock_processor()

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=True)
        self.processor.queue_manager.get_stale_mrs.return_value = [
            self.stale_item,
        ]

    async def when_check_stale_mrs_is_called(self):
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as self.mock_create_sm:
            await self.processor._check_stale_mrs()

    def then_state_machine_is_not_created(self):
        self.mock_create_sm.assert_not_awaited()

    def and_warning_flag_is_not_marked(self):
        self.processor.queue_manager.mark_stale_warning_sent.assert_not_awaited()
