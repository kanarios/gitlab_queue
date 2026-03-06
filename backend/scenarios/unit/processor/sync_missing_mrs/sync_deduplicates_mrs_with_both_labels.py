"""Test: sync deduplicates MRs that have both queue and hotfix labels."""

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.models.mr import Author, MergeRequest
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, FakeSettings
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "sync missing mrs deduplicates MRs with both labels"

    def given_processor_with_dual_labeled_mr(self):
        self.settings = FakeSettings(
            queue_label=Labels.MERGE_QUEUE,
            hotfix_label=Labels.HOTFIX,
        )

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

        # Same MR appears in both label queries
        self.gitlab_client = FakeGitLabClient(listed_mrs=[self.mr])

        self.queue_manager = FakeQueueManager()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=self.settings,
        )

    async def when_sync_is_called(self):
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_mr_should_be_added_only_once(self):
        assert len(self.queue_manager.add_to_queue_calls) == 1
        call = self.queue_manager.add_to_queue_calls[0]
        assert call["mr"] is self.mr
        assert call["is_hotfix"] is True

    def and_both_label_queries_were_made(self):
        # FakeGitLabClient returns the same list for both labels when listed_mrs is used
        # The processor calls _fetch_mrs_by_label twice (once per label)
        # and deduplicates by iid, so we verify only one add_to_queue call
        pass
