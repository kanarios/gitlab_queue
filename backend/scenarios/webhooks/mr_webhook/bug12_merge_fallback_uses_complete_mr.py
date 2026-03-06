"""BUG-12: merge fallback should use complete_mr, not remove_from_queue."""

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
from statemachine.exceptions import TransitionNotAllowed

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 456

_TRANSITION_ERROR = TransitionNotAllowed(
    type("FakeEvent", (), {"id": "merge_success", "name": "merge_success"})(),
    type("FakeState", (), {"id": "merging", "name": "merging"})(),
)


class Scenario(vedro.Scenario):
    subject = "merge fallback uses complete_mr instead of remove_from_queue"

    def given_handler_where_merge_transition_fails(self):
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

        self.fake_sm = FakeStateMachine(
            current_state=FakeCurrentState(id="merging"),
            trigger_errors={"merge_success": _TRANSITION_ERROR},
        )
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

    async def when_merge_event_triggers_transition_not_allowed(self):
        await self.handler.handle(self.event)

    def then_complete_mr_should_be_called(self):
        merged_calls = [
            c for c in self.queue_manager.complete_calls if c["mr_iid"] == MR_IID and c["status"] == "merged"
        ]
        assert len(merged_calls) == 1, (
            f"Expected complete_mr(MR_IID, status='merged'), got: {self.queue_manager.complete_calls}"
        )

    def and_remove_from_queue_should_not_be_called(self):
        assert self.queue_manager.remove_calls == [], (
            f"Expected no remove_from_queue calls, got: {self.queue_manager.remove_calls}"
        )
