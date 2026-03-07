"""Test: handle close uses state machine when notifier is available."""

from datetime import UTC, datetime

import vedro
from scenarios.fakes import FakeNotifier, FakeStateMachine, FakeStateMachineFactory
from scenarios.library import Labels

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "handle close triggers state machine for notification"

    def given_handler_with_notifier(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=123,
                title="Test",
                author_name="A",
                author_username="a",
                target_branch="master",
                state="queued",
                queued_at=datetime.now(UTC),
            )
        )

        self.notifier = FakeNotifier()

        self.fake_sm = FakeStateMachine()
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )
        self.event = create_mr_event(iid=123, action="close", state="closed")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_state_machine_should_be_created(self):
        assert len(self.sm_factory.calls) == 1

    def and_trigger_mark_removed_should_be_called_with_closed_reason(self):
        assert self.fake_sm.mark_removed_calls == [{"reason": "closed"}]

    def and_remove_from_queue_should_not_be_called_directly(self):
        assert self.queue_manager.remove_calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
