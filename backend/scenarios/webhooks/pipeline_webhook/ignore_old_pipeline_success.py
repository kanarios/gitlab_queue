"""Test: ignore old pipeline success webhook after rebase."""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import PipelineWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_notifier,
    create_mock_queue_manager,
    create_pipeline_event,
    create_queue_item_in_state,
    created_mock_settings,
)

OLD_PIPELINE_ID = 1000
NEW_PIPELINE_ID = 2000
MR_IID = 123


class Scenario(vedro.Scenario):
    subject = "ignore old pipeline success webhook after rebase"

    def given_handler_and_event(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport()
        self.queue_manager = create_mock_queue_manager()
        # Queue item tracking the NEW pipeline (after rebase)
        self.queue_manager.get_queue_item = AsyncMock(
            return_value=create_queue_item_in_state(
                "testing",
                retry_count=0,
                mr_iid=MR_IID,
                pipeline_id=NEW_PIPELINE_ID,
            )
        )
        self.notifier = create_mock_notifier()
        self.handler = PipelineWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        # Webhook from OLD pipeline (hypothetical late success webhook)
        self.event = create_pipeline_event(
            mr_iid=MR_IID,
            pipeline_id=OLD_PIPELINE_ID,
            status="success",
        )

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr") as mock_sm:
            mock_state_machine = MagicMock()
            mock_state_machine.trigger_pipeline_success = AsyncMock()
            mock_sm.return_value = mock_state_machine
            await self.handler.handle(self.event)
            self.mock_create_sm = mock_sm
            self.mock_state_machine = mock_state_machine

    def then_queue_item_should_be_checked(self):
        self.queue_manager.get_queue_item.assert_awaited_once_with(MR_IID)

    def and_state_machine_should_not_be_created(self):
        self.mock_create_sm.assert_not_awaited()

    def and_pipeline_success_should_not_be_triggered(self):
        self.mock_state_machine.trigger_pipeline_success.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
