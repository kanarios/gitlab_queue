"""Test: handle unlabeled without notifier checks remove_from_queue result.

BUG: When handler has no notifier, log.info("MR removed from queue via label removal")
is called unconditionally, even when remove_from_queue returns False.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import vedro
from scenarios.library import Labels

from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 123


class Scenario(vedro.Scenario):
    subject = "handle unlabeled without notifier checks removal result before logging"

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

    def given_unlabeled_event(self):
        self.event = create_mr_event(
            iid=MR_IID,
            action="unlabeled",
            previous_labels=[Labels.MERGE_QUEUE],
            current_labels=[],
            event_labels=[],
        )

    async def when_unlabeled_event_is_handled(self):
        with patch("gitlab_queue.webhooks.handlers.log") as self.mock_log:
            await self.handler.handle(self.event)

    def then_log_should_not_report_removal(self):
        removal_calls = [
            c
            for c in self.mock_log.info.call_args_list
            if c.args and c.args[0] == "MR removed from queue via label removal"
        ]
        assert len(removal_calls) == 0, "log.info should not report removal when remove_from_queue returns False"
