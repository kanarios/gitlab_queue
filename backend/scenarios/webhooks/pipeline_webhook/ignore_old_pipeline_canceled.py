"""Test: ignore old pipeline canceled webhook after rebase."""

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


class Scenario(vedro.Scenario):
    subject = "ignore old pipeline canceled webhook after rebase"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        # Queue item tracking the NEW pipeline (after rebase)
        self.queue_manager.add_item(
            create_queue_item_in_state(
                "testing",
                retry_count=0,
                mr_iid=MR_IID,
                pipeline_id=NEW_PIPELINE_ID,
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
        # Webhook from OLD pipeline (auto-canceled after rebase)
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            pipeline_id=OLD_PIPELINE_ID,
            status="canceled",
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_be_checked(self):
        assert any(
            c["project_id"] == self.event.project_id and c["mr_iid"] == MR_IID
            for c in self.queue_manager.get_queue_item_calls
        )

    def and_state_machine_should_not_be_created(self):
        assert self.sm_factory.calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
