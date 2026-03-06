"""BUG-17: External merge should not produce negative duration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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

        # Find the "merged" notification in FakeNotifier call recording
        self.duration = None
        for call in self.notifier.notify_calls:
            if call.get("status") == "merged":
                self.duration = call.get("duration")

    def then_duration_should_not_be_negative(self):
        assert self.duration is not None, "merged notification was not sent"
        # Duration string should not start with '-'
        assert not self.duration.startswith("-"), f"Duration is negative: {self.duration}"
