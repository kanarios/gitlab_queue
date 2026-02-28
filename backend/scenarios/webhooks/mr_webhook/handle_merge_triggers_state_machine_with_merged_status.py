"""Test: handle merge uses state machine to set merged status."""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import (
    create_gitlab_client_with_transport,
    create_mock_queue_manager,
    create_mock_settings,
    create_mr_event,
)


class Scenario(vedro.Scenario):
    subject = "handle merge triggers state machine with merged status"

    def given_handler_with_notifier(self):
        self.settings = create_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            state="merged",
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.queue_manager.get_queue_item = AsyncMock(return_value=MagicMock())

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.remove_queue_label = AsyncMock()

        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
        )
        self.event = create_mr_event(iid=123, action="merge", state="merged")

    async def when_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.create_state_machine_for_mr", new_callable=AsyncMock) as mock_sm:
            self.mock_state_machine = MagicMock()
            self.mock_state_machine.current_state.id = "merging"
            self.mock_state_machine.trigger_merge_success = AsyncMock()
            mock_sm.return_value = self.mock_state_machine
            self.mock_sm_factory = mock_sm
            await self.handler.handle(self.event)

    def then_state_machine_should_be_created(self):
        self.mock_sm_factory.assert_awaited_once()

    def and_trigger_merge_success_should_be_called(self):
        self.mock_state_machine.trigger_merge_success.assert_awaited_once()

    def and_remove_from_queue_should_not_be_called_directly(self):
        self.queue_manager.remove_from_queue.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
