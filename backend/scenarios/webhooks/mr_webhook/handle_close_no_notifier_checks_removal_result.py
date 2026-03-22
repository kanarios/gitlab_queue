"""Test: handle close without notifier checks remove_from_queue result.

BUG: When handler has no notifier, log.info("MR removed from queue after close")
is called unconditionally, even when remove_from_queue returns False.
"""

from datetime import UTC, datetime

import structlog.testing
import vedro
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.webhooks.handlers import MRWebhookHandler

from ._helpers import create_mock_settings, create_mr_event

MR_IID = 456


class Scenario(vedro.Scenario):
    subject = "handle close without notifier checks removal result before logging"

    def given_settings(self):
        self.settings = create_mock_settings()

    def given_gitlab_client(self):
        self.gitlab_client = FakeGitLabClient()

    def given_queue_manager_with_failed_removal(self):
        # Simulate race: get_queue_item returns an item but remove_from_queue returns False
        phantom_item = QueueItem(
            mr_iid=MR_IID,
            title="Test",
            author_name="A",
            author_username="a",
            target_branch="main",
            state="queued",
            queued_at=datetime.now(UTC),
        )
        self.queue_manager = FakeQueueManager(
            get_queue_item_sequence=[phantom_item],
        )
        # Item is NOT in _items, so remove_from_queue will return False

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
        with structlog.testing.capture_logs() as self.captured:
            await self.handler.handle(self.event)

    def then_remove_from_queue_was_called(self):
        assert any(
            c["project_id"] == self.event.project_id and c["mr_iid"] == MR_IID for c in self.queue_manager.remove_calls
        )

    def and_log_should_not_report_removal(self):
        removal_entries = [e for e in self.captured if e.get("event") == "MR removed from queue after close"]
        assert len(removal_entries) == 0, "log.info should not report removal when remove_from_queue returns False"
