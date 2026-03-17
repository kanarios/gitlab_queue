"""Test: older pipeline success webhook is rejected (existing behavior)."""

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

NEW_PIPELINE_ID = 2000
OLDER_PIPELINE_ID = 500
MR_IID = 123
EXPECTED_SHA = "abc123def456"


class Scenario(vedro.Scenario):
    subject = "older pipeline success webhook is rejected"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(
            create_queue_item_in_state(
                "testing",
                mr_iid=MR_IID,
                pipeline_id=NEW_PIPELINE_ID,
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
        # Webhook from OLDER pipeline
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            pipeline_id=OLDER_PIPELINE_ID,
            status="success",
            sha=EXPECTED_SHA,
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_state_machine_should_not_be_created(self):
        assert self.sm_factory.calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
