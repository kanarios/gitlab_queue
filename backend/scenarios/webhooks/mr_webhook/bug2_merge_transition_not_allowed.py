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
    subject = "merge handler catches TransitionNotAllowed"

    def given_handler_with_mr_in_queue(self):
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
            state_machine_factory=self.sm_factory,
        )
        self.event = create_mr_event(iid=MR_IID, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        self.exc = None
        try:
            await self.handler.handle(self.event)
        except Exception as e:
            self.exc = e

    def then_no_exception_is_propagated(self):
        assert self.exc is None, f"Expected no exception, got: {self.exc!r}"
