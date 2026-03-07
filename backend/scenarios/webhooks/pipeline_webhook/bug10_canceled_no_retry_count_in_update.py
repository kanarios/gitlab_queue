"""BUG-10: _handle_canceled should NOT pass retry_count to update_mr_state (double increment)."""

from __future__ import annotations

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
        self.queue_manager.add_item(self.queue_item)

        self.sm_factory = FakeStateMachineFactory()

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
            state_machine_factory=self.sm_factory,
        )
        self.event = create_pipeline_event(
            pipeline_id=456,
            mr_iid=123,
            status="canceled",
            sha=self.queue_item.expected_sha,
        )

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_update_should_not_contain_retry_count(self):
        assert len(self.queue_manager.update_state_calls) >= 1, "update_mr_state was not called"
        call = self.queue_manager.update_state_calls[0]
        assert "retry_count" not in call, f"update_mr_state should not pass retry_count, got: {call}"

    async def cleanup(self):
        await self.gitlab_client.close()
