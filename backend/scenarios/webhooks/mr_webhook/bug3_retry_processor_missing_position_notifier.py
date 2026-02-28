from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.retry_processor import WebhookRetryProcessor

from ._helpers import create_mr_event


class Scenario(vedro.Scenario):
    subject = "retry processor passes position_notifier to MRWebhookHandler"

    def given_retry_processor_with_position_notifier(self):
        self.position_notifier = MagicMock()

        self.processor = WebhookRetryProcessor(
            retry_manager=MagicMock(),
            settings=MagicMock(),
            gitlab_client=MagicMock(),
            queue_manager=MagicMock(),
            notifier=MagicMock(),
        )

        # Even before the fix, we can attach the attribute; the bug is that it's not used.
        self.processor.position_notifier = self.position_notifier

        self.event = create_mr_event(iid=42, action="update", state="opened")

    async def when_retry_processor_handles_mr_event(self):
        with patch("gitlab_queue.webhooks.handlers.MRWebhookHandler") as mock_handler_cls:
            mock_handler = MagicMock()
            mock_handler.handle = AsyncMock()
            mock_handler_cls.return_value = mock_handler

            await self.processor._handle_mr_event(self.event)

            self.mock_handler_cls = mock_handler_cls

    def then_handler_is_created_with_position_notifier(self):
        kwargs = self.mock_handler_cls.call_args.kwargs
        assert kwargs.get("position_notifier") is self.position_notifier, (
            "Expected MRWebhookHandler(..., position_notifier=<provided>) "
            f"but got position_notifier={kwargs.get('position_notifier')!r}"
        )
