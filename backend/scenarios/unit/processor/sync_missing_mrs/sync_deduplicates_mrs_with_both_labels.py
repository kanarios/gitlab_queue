"""Test: sync deduplicates MRs that have both queue and hotfix labels."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "sync missing mrs deduplicates MRs with both labels"

    def given_processor_with_dual_labeled_mr(self):
        self.settings = MagicMock()
        self.settings.queue_label = Labels.MERGE_QUEUE
        self.settings.hotfix_label = Labels.HOTFIX

        self.mr = MergeRequest(
            iid=42,
            title="Important MR",
            state="opened",
            labels=[Labels.MERGE_QUEUE, Labels.HOTFIX],
            sha="abc123",
            source_branch="feature",
            target_branch="main",
            merge_status="can_be_merged",
            author=Author(id=1, name="Dev", username="dev"),
        )

        self.gitlab_client = MagicMock()
        # Same MR appears in both lists
        self.gitlab_client.list_mrs_with_label = AsyncMock(return_value=[self.mr])

        self.queue_manager = MagicMock()
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.add_to_queue = AsyncMock()

        self.notifier = AsyncMock()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            settings=self.settings,
        )

    async def when_sync_is_called(self):
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_mr_should_be_added_only_once(self):
        self.queue_manager.add_to_queue.assert_awaited_once_with(self.mr, is_hotfix=True)

    def and_both_label_queries_were_made(self):
        self.gitlab_client.list_mrs_with_label.assert_any_await(Labels.MERGE_QUEUE, state="opened")
        self.gitlab_client.list_mrs_with_label.assert_any_await(Labels.HOTFIX, state="opened")
        assert self.gitlab_client.list_mrs_with_label.await_count == 2
