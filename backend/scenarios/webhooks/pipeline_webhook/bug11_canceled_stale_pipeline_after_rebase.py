"""BUG-11: Canceled pipeline after rebase should be ignored (stale pipeline)."""

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
    subject = "canceled stale pipeline after rebase is ignored"

    def given_handler_with_pipeline_mismatch_after_rebase(self):
        self.settings = create_mock_settings()
        self.settings.pipeline_retry_count = 2
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()

        # First call to get_queue_item (from _validate_pipeline_event) returns pipeline_id=100
        self.old_item = create_queue_item_in_state(
            "testing",
            retry_count=0,
            mr_iid=123,
            pipeline_id=100,
        )
        # Second call (re-fetch) returns pipeline_id=200 — rebase happened
        self.new_item = create_queue_item_in_state(
            "testing",
            retry_count=0,
            mr_iid=123,
            pipeline_id=200,
        )
        self.queue_manager.get_queue_item_sequence = [self.old_item, self.new_item]

        self.sm_factory = FakeStateMachineFactory()

        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=create_mock_notifier(),
            state_machine_factory=self.sm_factory,
        )

        # Webhook arrives for OLD pipeline_id=100
        self.event = create_pipeline_event(
            pipeline_id=100,
            mr_iid=123,
            status="canceled",
            sha=self.old_item.expected_sha,
        )

    async def when_canceled_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_update_mr_state_should_not_be_called(self):
        assert self.queue_manager.update_state_calls == []

    def and_state_machine_should_not_be_created(self):
        assert self.sm_factory.calls == []

    async def cleanup(self):
        await self.gitlab_client.close()
