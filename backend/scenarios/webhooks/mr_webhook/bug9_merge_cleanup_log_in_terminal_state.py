"""Test: _handle_merge does NOT log 'cleaned up' for terminal state MR."""

from __future__ import annotations

import structlog.testing
import vedro
from scenarios.fakes import FakeCurrentState, FakeGitLabClient, FakeNotifier, FakeStateMachine, FakeStateMachineFactory
from scenarios.webhooks.pipeline_webhook._helpers import create_queue_item_in_state

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "_handle_merge does not log 'MR cleaned up' when MR is in terminal state"

    def given_handler_with_terminal_state_mr(self):
        self.settings = create_mock_settings()
        self.gitlab_client = FakeGitLabClient()
        self.queue_manager = create_mock_queue_manager()
        self.queue_item = create_queue_item_in_state("merged", mr_iid=123)
        self.queue_manager.add_item(self.queue_item)

        self.notifier = FakeNotifier()

        self.fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="merged"))
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )

        self.event = create_mr_event(iid=123, action="merge", state="merged")

    async def when_merge_event_is_handled(self):
        with structlog.testing.capture_logs() as self.captured:
            await self.handler._handle_merge(self.event)

    def then_cleanup_message_should_not_be_logged(self):
        for entry in self.captured:
            msg = entry.get("event", "")
            assert "cleaned up" not in msg.lower(), f"Unexpected 'cleaned up' log for terminal state MR: {entry}"
