"""Test _check_stale_mrs sends warning for stale MR.

When an MR has been in the queue longer than the warning threshold and
has not yet been warned, a stale warning notification should be sent
and the warning flag should be marked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "check stale mrs sends warning for unwarned stale MR"

    def given_processor_with_stale_unwarned_mr(self):
        self.processor = create_mock_processor()

        self.stale_item = create_test_queue_item(mr_iid=42, state="queued", stale_warning_sent=False)
        self.processor.queue_manager.get_stale_mrs.return_value = [
            self.stale_item,
        ]

        self.mock_sm = create_mock_state_machine()

    async def when_check_stale_mrs_is_called(self):
        with patch(
            "gitlab_queue.core.processor.create_state_machine_for_mr",
            new_callable=AsyncMock,
            return_value=self.mock_sm,
        ):
            await self.processor._check_stale_mrs()

    def then_stale_warning_is_sent(self):
        self.mock_sm.notify_stale_warning.assert_awaited_once_with(
            warning_hours=24,
        )

    def and_warning_flag_is_marked(self):
        self.processor.queue_manager.mark_stale_warning_sent.assert_awaited_once_with(
            42,
        )
