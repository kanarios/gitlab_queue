"""Test _process_mr removes MR when _verify_mr_in_queue returns False.

Lines 293-295: when MR no longer has queue label, trigger_mark_removed and return REMOVED.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "process mr removes MR when verify returns False"

    def given_processor_where_mr_label_was_removed(self):
        self.processor = create_mock_processor()
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.mock_sm = create_mock_state_machine()

    async def when_process_mr_is_called_with_label_removed(self):
        with (
            patch(
                "gitlab_queue.core.processor.create_state_machine_for_mr",
                new_callable=AsyncMock,
                return_value=self.mock_sm,
            ),
            patch.object(
                self.processor,
                "_verify_mr_in_queue",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_trigger_mark_removed_was_called(self):
        self.mock_sm.trigger_mark_removed.assert_awaited_once_with(reason="label_removed")
