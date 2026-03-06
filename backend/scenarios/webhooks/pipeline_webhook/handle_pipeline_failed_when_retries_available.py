"""Test: handle pipeline failed when retries available."""

import vedro

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
    subject = "handle pipeline failed when retries available"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.settings.job_retry_count = 3
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.add_item(create_queue_item_in_state("testing", retry_count=1, mr_iid=123))
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=123, status="failed")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_marked_as_failed(self):
        assert len(self.queue_manager.update_state_calls) == 1
        call = self.queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 123
        assert call["state"] == "testing"
        assert call["pipeline_status"] == "failed"

    async def cleanup(self):
        await self.gitlab_client.close()
