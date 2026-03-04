"""BUG-10: _handle_canceled should NOT pass retry_count to update_mr_state (double increment)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    subject = "pipeline canceled does not pass retry_count to update_mr_state"

    def given_handler_with_retries_available(self):
        self.settings = create_mock_settings()
        self.settings.job_retry_count = 2
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        self.queue_item = create_queue_item_in_state(
            "testing",
            retry_count=0,
            mr_iid=123,
            pipeline_id=456,
        )
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
        )
        self.event = create_pipeline_event(
            pipeline_id=456,
            mr_iid=123,
            status="canceled",
            sha=self.queue_item.expected_sha,
        )

    async def when_event_is_handled(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new=AsyncMock(),
        ):
            await self.handler.handle(self.event)

    def then_update_should_not_contain_retry_count(self):
        call_kwargs = self.queue_manager.update_mr_state.call_args
        assert call_kwargs is not None, "update_mr_state was not called"
        _, kwargs = call_kwargs
        assert "retry_count" not in kwargs, f"update_mr_state should not pass retry_count, got kwargs: {kwargs}"

    async def cleanup(self):
        await self.gitlab_client.close()
