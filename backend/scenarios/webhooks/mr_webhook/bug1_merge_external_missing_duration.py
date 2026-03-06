from __future__ import annotations

from datetime import UTC, datetime

import vedro
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeStateMachine,
    FakeStateMachineFactory,
)

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

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

        self.gitlab_client = FakeGitLabClient()
        self.notifier = FakeNotifier()

        self.fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="queued"))
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )

        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_merged_notification_includes_duration_kwarg(self):
        merged_calls = [c for c in self.notifier.notify_calls if c.get("status") == "merged"]
        assert merged_calls, "Expected notifier.notify to be called with 'merged' status"

        assert "duration" in merged_calls[0], (
            f"Expected 'duration' in notify kwargs, got: {sorted(merged_calls[0].keys())}"
        )
        assert merged_calls[0]["duration"] is not None, "Expected 'duration' to have a value"
