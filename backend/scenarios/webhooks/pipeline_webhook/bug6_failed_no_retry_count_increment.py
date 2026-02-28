from __future__ import annotations

from unittest.mock import AsyncMock

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
    subject = "pipeline failed updates pipeline_status without incrementing retry_count"

    def given_handler_and_failed_event(self):
        self.settings = create_mock_settings()
        self.settings.pipeline_retry_count = 2

        self.gitlab_client, self.transport = create_gitlab_client_with_transport()

        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state("testing", retry_count=0, mr_iid=123)
        )

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(mr_iid=123, status="failed")

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_pipeline_status_is_set_to_failed(self):
        self.queue_manager.update_mr_state.assert_awaited_once_with(
            123,
            "testing",
            pipeline_status="failed",
        )

    async def cleanup(self):
        await self.gitlab_client.close()
