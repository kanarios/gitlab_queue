"""Test: notification failure after adding MR to queue is swallowed.

When the position notifier raises an exception after an MR is added to the queue,
the error should be caught and logged but not propagated. The MR should still
be successfully added to the queue.
Covers handlers.py _notify_position_after_add exception handling (lines 67-78).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mr_event,
    created_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "notification failure after adding MR is swallowed"

    def given_handler_with_failing_notifier(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_length = AsyncMock(return_value=0)

        # Create a position notifier that fails on notify_initial_position
        self.position_notifier = MagicMock()
        self.position_notifier.capture_queue_positions = AsyncMock(return_value={})
        self.position_notifier.notify_initial_position = AsyncMock(
            side_effect=Exception("Notification service unavailable")
        )

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            position_notifier=self.position_notifier,
        )
        self.event = create_mr_event(
            iid=123,
            action="labeled",
            previous_labels=[],
            current_labels=[Labels.MERGE_QUEUE],
            event_labels=[Labels.MERGE_QUEUE],
        )

    async def when_event_is_handled(self):
        # Should not raise despite notification failure
        await self.handler.handle(self.event)

    def then_mr_should_still_be_added_to_queue(self):
        self.queue_manager.add_to_queue.assert_called_once()

    def and_notification_should_have_been_attempted(self):
        self.position_notifier.notify_initial_position.assert_called_once_with(123)

    async def cleanup(self):
        await self.gitlab_client.close()
