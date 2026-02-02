"""Scenario: remove queue label handles GitLab API error gracefully."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler


class Scenario(vedro.Scenario):
    subject = "remove queue label handles GitLab API error gracefully"

    def given_settings(self):
        self.settings = MagicMock()
        self.settings.queue_label = "merge_queue"
        self.settings.hotfix_label = "hotfix"

    def given_gitlab_client_that_fails(self):
        self.gitlab_client = AsyncMock()
        self.gitlab_client.remove_mr_label.side_effect = Exception("API error")

    def given_queue_manager(self):
        self.queue_manager = AsyncMock()

    def given_handler(self):
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    async def when_remove_queue_label_is_called(self):
        await self.handler._remove_queue_label(123)

    def then_it_completes_and_calls_gitlab_client(self):
        self.gitlab_client.remove_mr_label.assert_called_once_with(123, "merge_queue")
