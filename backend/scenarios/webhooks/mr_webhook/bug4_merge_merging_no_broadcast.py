"""BUG-4: merge in merging state should broadcast websocket queue update.

Bug: When MR merge webhook arrives while in 'merging' state, the websocket
broadcast was being skipped.

Fix: Handler now ensures broadcast_queue_updated is called after handling.
"""

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
    FakeWebSocketManager,
)

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 789


class Scenario(vedro.Scenario):
    subject = "merge in merging state broadcasts websocket queue update"

    def given_handler_with_websocket_manager(self):
        self.settings = create_mock_settings()

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=MR_IID,
                title="Test",
                author_name="A",
                author_username="a",
                target_branch="main",
                state="merging",
                queued_at=datetime.now(UTC),
            )
        )

        self.gitlab_client = FakeGitLabClient()
        self.notifier = FakeNotifier()
        self.websocket_manager = FakeWebSocketManager()

        self.fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="merging"))
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            websocket_manager=self.websocket_manager,
            state_machine_factory=self.sm_factory,
        )
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_websocket_broadcast_queue_updated_is_called(self):
        queue_updated = [c for c in self.websocket_manager.broadcast_calls if c.get("type") == "queue_updated"]
        assert len(queue_updated) > 0, (
            f"Expected broadcast_queue_updated call, got: {self.websocket_manager.broadcast_calls}"
        )
