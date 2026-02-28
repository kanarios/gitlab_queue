from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 123


class Scenario(vedro.Scenario):
    subject = "merge external requires duration in notification"

    def given_handler_with_queue_item_in_queued_state(self):
        self.settings = create_mock_settings()

        self.queue_item = QueueItem(
            mr_iid=MR_IID,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="queued",
            queued_at=datetime.now(UTC),
        )

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.queue_manager.complete_mr = AsyncMock(return_value=True)

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
        # Force the code path for "merged externally while queued/rebasing/testing"
        # without running real state machine callbacks.
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            sm = MagicMock()
            sm.current_state.id = "queued"
            mock_sm.return_value = sm

            await self.handler.handle(self.event)

    def then_merged_notification_includes_duration_kwarg(self):
        merged_calls = [c for c in self.notifier.notify.await_args_list if c.args[1] == "merged"]
        assert merged_calls, "Expected notifier.notify to be called with 'merged' status"

        call_kwargs = merged_calls[0].kwargs
        assert "duration" in call_kwargs, f"Expected 'duration' in notify kwargs, got: {sorted(call_kwargs.keys())}"
        assert call_kwargs["duration"] is not None, "Expected 'duration' to have a value"
