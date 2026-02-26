"""Test: sync adds MRs that only have hotfix label."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "sync missing mrs adds hotfix-only MRs to queue"

    def given_processor_with_hotfix_only_mr(self):
        self.settings = MagicMock()
        self.settings.queue_label = Labels.MERGE_QUEUE
        self.settings.hotfix_label = Labels.HOTFIX

        self.hotfix_mr = MergeRequest(
            iid=99,
            title="Hotfix MR",
            state="opened",
            labels=[Labels.HOTFIX],
            sha="abc123",
            source_branch="hotfix/fix",
            target_branch="main",
            merge_status="can_be_merged",
            author=Author(id=1, name="Dev", username="dev"),
        )

        self.gitlab_client = MagicMock()
        # Queue label returns empty list
        # Hotfix label returns one MR
        self.gitlab_client.list_mrs_with_label = AsyncMock(
            side_effect=lambda label, **_kwargs: [self.hotfix_mr] if label == Labels.HOTFIX else []
        )

        self.queue_manager = MagicMock()
        self.queue_manager.get_active_queue = AsyncMock(return_value=[])
        self.queue_manager.add_to_queue = AsyncMock()

        self.notifier = MagicMock()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            settings=self.settings,
        )

    async def when_sync_is_called(self):
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_hotfix_mr_should_be_added_to_queue(self):
        self.queue_manager.add_to_queue.assert_awaited_once_with(self.hotfix_mr, is_hotfix=True)
