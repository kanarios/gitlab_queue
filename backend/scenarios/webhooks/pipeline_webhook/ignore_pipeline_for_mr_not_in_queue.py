"""Test: ignore pipeline for MR not in queue."""

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_mock_settings,
    create_pipeline_event,
)


class Scenario(vedro.Scenario):
    subject = "ignore pipeline for MR not in queue"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        # MR not in queue (default for FakeQueueManager)
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_queue_item_should_be_checked(self):
        assert any(
            c["project_id"] == self.event.project_id and c["mr_iid"] == 123
            for c in self.queue_manager.get_queue_item_calls
        )

    def and_no_state_update_should_happen(self):
        assert self.queue_manager.update_state_calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
