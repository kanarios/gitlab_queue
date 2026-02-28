"""BUG-17: External merge should not produce negative duration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 555


class Scenario(vedro.Scenario):
    subject = "external merge does not produce negative duration"

    def given_handler_with_future_queued_at(self):
        self.settings = create_mock_settings()

        # Create queue item with queued_at in the FUTURE
        self.queue_item = QueueItem(
            mr_iid=MR_IID,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="queued",
            queued_at=datetime.now(UTC) + timedelta(hours=1),
        )

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.queue_manager.complete_mr = AsyncMock(return_value=True)
        self.queue_manager.get_queue_length = AsyncMock(return_value=1)

        self.gitlab_client = MagicMock()
        self.gitlab_client.remove_mr_label = AsyncMock()

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.current_state.id = "queued"
            mock_sm.return_value = sm

            await self.handler.handle(self.event)

        # Capture the duration passed to notifier
        notify_calls = self.notifier.notify.call_args_list
        self.duration = None
        for c in notify_calls:
            status = c.args[1] if len(c.args) >= 2 else c.kwargs.get("status")
            if status == "merged":
                self.duration = c.kwargs.get("duration")

    def then_duration_should_not_be_negative(self):
        assert self.duration is not None, "merged notification was not sent"
        # Duration string should not start with '-'
        assert not self.duration.startswith("-"), f"Duration is negative: {self.duration}"
