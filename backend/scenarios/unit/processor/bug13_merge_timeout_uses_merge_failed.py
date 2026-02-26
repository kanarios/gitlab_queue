"""BUG-13: Merge timeout should call trigger_merge_failed, not trigger_timeout."""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from scenarios.unit.processor._helpers import (
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "merge timeout calls trigger_merge_failed instead of trigger_timeout"

    def given_processor_with_merge_timeout(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

        settings = create_mock_settings(merge_timeout_seconds=1)
        self.processor = create_mock_processor(settings=settings)

        # Make merge_mr raise TimeoutError (simulates asyncio.wait_for timeout)
        self.processor.gitlab_client.merge_mr = AsyncMock(side_effect=TimeoutError("merge timed out"))

        # Queue item for expected_sha lookup
        self.processor.queue_manager.get_queue_item = AsyncMock(
            return_value=create_test_queue_item(mr_iid=42, state="merging")
        )

    async def when_merge_times_out(self):
        await self.processor._process_merge(self.ctx)

    def then_trigger_merge_failed_should_be_called(self):
        self.sm.trigger_merge_failed.assert_awaited_once()

    def and_trigger_timeout_should_not_be_called(self):
        self.sm.trigger_timeout.assert_not_awaited()
