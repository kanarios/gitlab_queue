from __future__ import annotations

import vedro
from scenarios.fakes import (
    FakeGitLabClient,
    FakeHandlerFactory,
    FakeNotifier,
    FakePositionNotifier,
    FakeQueueManager,
    FakeRetryManager,
)

from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor

from ._helpers import create_mock_settings, create_mr_event

_STUB = object()


class Scenario(vedro.Scenario):
    subject = "retry processor passes position_notifier to MRWebhookHandler"

    def given_retry_processor_with_position_notifier(self):
        self.position_notifier = FakePositionNotifier()
        self.mr_handler_factory = FakeHandlerFactory()

        self.processor = WebhookRetryProcessor(
            retry_manager=FakeRetryManager(),
            settings=create_mock_settings(),
            gitlab_client=FakeGitLabClient(),
            queue_manager=FakeQueueManager(),
            notifier=FakeNotifier(),
            mr_handler_factory=self.mr_handler_factory,
        )

        self.processor.position_notifier = self.position_notifier

        self.event = create_mr_event(iid=42, action="update", state="opened")

    async def when_retry_processor_handles_mr_event(self):
        await self.processor._handle_mr_event(self.event)

    def then_handler_is_created_with_position_notifier(self):
        kwargs = self.mr_handler_factory.calls[0]
        assert kwargs.get("position_notifier") is self.position_notifier, (
            "Expected MRWebhookHandler(..., position_notifier=<provided>) "
            f"but got position_notifier={kwargs.get('position_notifier')!r}"
        )
