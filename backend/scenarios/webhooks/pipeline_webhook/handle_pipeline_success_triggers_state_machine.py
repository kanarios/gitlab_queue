"""Test: handle pipeline success triggers state machine."""

import vedro
from scenarios.fakes import FakeCurrentState, FakeStateMachine, FakeStateMachineFactory

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
    subject = "handle pipeline success triggers state machine"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(create_queue_item_in_state("testing", mr_iid=123))
        self.notifier = create_mock_notifier()

        self.fake_sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.sm_factory = FakeStateMachineFactory(state_machine=self.fake_sm)

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

    def then_state_machine_should_be_created(self):
        assert len(self.sm_factory.calls) == 1

    def and_pipeline_success_should_be_triggered(self):
        assert len(self.fake_sm.pipeline_success_calls) == 1

    async def cleanup(self):
        await self.gitlab_client.close()
