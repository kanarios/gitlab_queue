"""Scenario: remove queue label handles GitLab API error gracefully."""

import vedro
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings


class Scenario(vedro.Scenario):
    subject = "remove queue label handles GitLab API error gracefully"

    def given_settings(self):
        self.settings = create_mock_settings()

    def given_gitlab_client_that_fails(self):
        self.gitlab_client = FakeGitLabClient(
            remove_label_error=Exception("API error"),
        )

    def given_queue_manager(self):
        self.queue_manager = FakeQueueManager()

    def given_handler(self):
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    async def when_remove_queue_label_is_called(self):
        await self.handler._remove_queue_label(123)

    def then_it_completes_and_calls_gitlab_client(self):
        assert (123, "merge_queue") in self.gitlab_client.remove_label_calls
