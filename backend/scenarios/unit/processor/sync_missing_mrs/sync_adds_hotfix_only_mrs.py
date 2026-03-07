"""Test: sync adds MRs that only have hotfix label."""

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, FakeSettings
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "sync missing mrs adds hotfix-only MRs to queue"

    def given_processor_with_hotfix_only_mr(self):
        self.settings = FakeSettings(
            queue_label=Labels.MERGE_QUEUE,
            hotfix_label=Labels.HOTFIX,
        )

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

        self.gitlab_client = FakeGitLabClient(
            listed_mrs_by_label={
                Labels.MERGE_QUEUE: [],
                Labels.HOTFIX: [self.hotfix_mr],
            },
        )

        self.queue_manager = FakeQueueManager()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=self.settings,
        )

    async def when_sync_is_called(self):
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_hotfix_mr_should_be_added_to_queue(self):
        assert len(self.queue_manager.add_to_queue_calls) == 1
        call = self.queue_manager.add_to_queue_calls[0]
        assert call["mr"] is self.hotfix_mr
        assert call["is_hotfix"] is True
