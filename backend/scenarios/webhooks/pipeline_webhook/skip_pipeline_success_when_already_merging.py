"""Test: skip pipeline success transition when MR is already in merging state."""

import vedro
from scenarios.fakes import FakeStateMachineFactory

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
    create_queue_item_in_state,
)


class Scenario(vedro.Scenario):
    subject = "skip pipeline success when MR already in merging state"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()

        # First call (from _validate_pipeline_event) returns "testing",
        # second call (re-fetch) returns "merging" — simulates concurrent state change
        testing_item = create_queue_item_in_state("testing", mr_iid=123)
        merging_item = create_queue_item_in_state("merging", mr_iid=123)
        self.queue_manager.get_queue_item_sequence = [testing_item, merging_item]
        self.notifier = create_mock_notifier()

        self.sm_factory = FakeStateMachineFactory()

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_state_machine_should_not_be_created(self):
        assert self.sm_factory.calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
