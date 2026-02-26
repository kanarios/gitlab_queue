"""Test: skip pipeline success transition when MR is already in merging state."""

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
    subject = "skip pipeline success when MR already in merging state"

    def given_handler_and_event(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()

        # First call (from _validate_pipeline_event) returns "testing",
        # second call (re-fetch) returns "merging" — simulates concurrent state change
        testing_item = create_queue_item_in_state("testing", mr_iid=123)
        merging_item = create_queue_item_in_state("merging", mr_iid=123)
        self.queue_manager.get_queue_item = AsyncMock(side_effect=[testing_item, merging_item])
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_pipeline_event(mr_iid=123, status="success")

    async def when_event_is_handled(self):
        with patch(
            "gitlab_queue.webhooks.handlers.create_state_machine_for_mr",
            new_callable=AsyncMock,
        ) as mock_sm:
            await self.handler.handle(self.event)
            self.mock_sm = mock_sm

    def then_state_machine_should_not_be_created(self):
        self.mock_sm.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
