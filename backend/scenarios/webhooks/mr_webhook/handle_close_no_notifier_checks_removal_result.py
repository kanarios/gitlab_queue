"""Test: handle close without notifier checks remove_from_queue result.

BUG: When handler has no notifier, log.info("MR removed from queue after close")
is called unconditionally, even when remove_from_queue returns False.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 456


class Scenario(vedro.Scenario):
    subject = "handle close without notifier checks removal result before logging"

    def given_settings(self):
        self.settings = create_mock_settings()

    def given_gitlab_client(self):
        self.gitlab_client = AsyncMock()

    def given_queue_manager_with_failed_removal(self):
        self.queue_manager = AsyncMock()
        self.queue_manager.get_queue_item.return_value = MagicMock()
        self.queue_manager.remove_from_queue.return_value = False

    def given_handler_without_notifier(self):
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )

    def given_close_event(self):
        self.event = create_mr_event(
            iid=MR_IID,
            action="close",
            state="closed",
        )

    async def when_close_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.log") as self.mock_log:
            await self.handler.handle(self.event)

    def then_remove_from_queue_was_called(self):
        self.queue_manager.remove_from_queue.assert_awaited_once()

    def and_log_should_not_report_removal(self):
        removal_calls = [
            c for c in self.mock_log.info.call_args_list if c.args and c.args[0] == "MR removed from queue after close"
        ]
        assert len(removal_calls) == 0, "log.info should not report removal when remove_from_queue returns False"
