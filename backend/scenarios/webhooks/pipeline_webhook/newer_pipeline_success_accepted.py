"""Test: newer pipeline success webhook is accepted and triggers state machine."""

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

OLD_PIPELINE_ID = 1000
NEW_PIPELINE_ID = 2000
MR_IID = 123
EXPECTED_SHA = "abc123def456"


class Scenario(vedro.Scenario):
    subject = "newer pipeline success webhook is accepted when SHA matches"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        # Queue item tracking the OLD pipeline with expected_sha set
        self.queue_manager.add_item(
            create_queue_item_in_state(
                "testing",
                mr_iid=MR_IID,
                pipeline_id=OLD_PIPELINE_ID,
                expected_sha=EXPECTED_SHA,
            )
        )
        self.notifier = create_mock_notifier()
        self.sm_factory = FakeStateMachineFactory()

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            state_machine_factory=self.sm_factory,
        )
        # Webhook from NEWER pipeline with matching SHA
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            pipeline_id=NEW_PIPELINE_ID,
            status="success",
            sha=EXPECTED_SHA,
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_pipeline_id_should_be_updated(self):
        # First update_state call: switching to newer pipeline
        switch_calls = [c for c in self.queue_manager.update_state_calls if c.get("pipeline_id") == NEW_PIPELINE_ID]
        assert len(switch_calls) >= 1

    def then_state_machine_should_be_triggered(self):
        assert len(self.sm_factory.calls) >= 1

    async def cleanup(self):
        await self.gitlab_client.close()
