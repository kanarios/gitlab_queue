"""Test create_retry_processor factory function returns a WebhookRetryProcessor."""

from __future__ import annotations

from unittest.mock import MagicMock

import vedro

from gitlab_queue.webhooks.retry_processor import (
    WebhookRetryProcessor,
    create_retry_processor,
)

from ._helpers import (
    create_mock_retry_manager,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "create_retry_processor returns a configured WebhookRetryProcessor instance"

    def given_dependencies(self):
        self.retry_manager = create_mock_retry_manager()
        self.settings = create_mock_settings()
        self.gitlab_client = MagicMock()
        self.queue_manager = MagicMock()
        self.notifier = MagicMock()
        self.websocket_manager = MagicMock()

    def when_create_retry_processor_is_called(self):
        self.processor = create_retry_processor(
            retry_manager=self.retry_manager,
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            websocket_manager=self.websocket_manager,
        )

    def then_result_is_webhook_retry_processor(self):
        assert isinstance(self.processor, WebhookRetryProcessor)

    def and_retry_manager_is_set(self):
        assert self.processor.retry_manager is self.retry_manager

    def and_settings_is_set(self):
        assert self.processor.settings is self.settings

    def and_gitlab_client_is_set(self):
        assert self.processor.gitlab_client is self.gitlab_client

    def and_queue_manager_is_set(self):
        assert self.processor.queue_manager is self.queue_manager

    def and_notifier_is_set(self):
        assert self.processor.notifier is self.notifier

    def and_websocket_manager_is_set(self):
        assert self.processor.websocket_manager is self.websocket_manager
