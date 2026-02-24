"""Test: handle unknown action is ignored."""

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler
from scenarios.library import Labels

from ._helpers import (create_gitlab_client_with_transport,
                       create_mock_queue_manager, create_mr_event,
                       created_mock_settings)


class Scenario(vedro.Scenario):
    subject = "handle unknown action is ignored"

    def given_handler(self):
        self.settings = created_mock_settings()
        self.gitlab_client, self.transport = create_gitlab_client_with_transport(
            mr_iid=123,
            labels=[Labels.MERGE_QUEUE],
        )
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        self.event = create_mr_event(iid=123, action="approved")  # Unknown action

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_no_queue_operations_should_happen(self):
        self.queue_manager.add_to_queue.assert_not_awaited()
        self.queue_manager.remove_from_queue.assert_not_awaited()
        self.queue_manager.update_mr_state.assert_not_awaited()

    async def cleanup(self):
        await self.gitlab_client.close()
