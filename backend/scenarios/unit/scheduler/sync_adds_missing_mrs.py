"""Test scenario: sync operation adds MRs missing from local queue."""

from __future__ import annotations

import vedro

from gitlab_queue.core.scheduler import QueueScheduler
from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings, create_mr


class Scenario(vedro.Scenario):
    subject = "sync adds mrs that are in gitlab but missing from queue"

    def given_scheduler_with_missing_mrs(self):
        self.gitlab_client = FakeGitLabClient()

        # GitLab returns two MRs with queue label
        self.gitlab_mrs = [
            create_mr(iid=10, labels=["merge_queue"]),
            create_mr(iid=20, labels=["merge_queue"]),
        ]
        self.gitlab_client.listed_mrs_by_label = {
            "merge_queue": self.gitlab_mrs,
            # hotfix label returns empty
        }

        self.queue_manager = FakeQueueManager()
        # Queue is currently empty - both MRs are "missing"

        self.settings = FakeSettings()
        self.scheduler = QueueScheduler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=self.settings,
        )

    async def when_sync_is_performed(self):
        self.stats = await self.scheduler.sync_queue()

    def then_added_count_should_be_two(self):
        assert self.stats.added == 2

    def and_queue_manager_should_have_added_both_mrs(self):
        assert len(self.queue_manager.add_to_queue_calls) == 2

    def and_mrs_in_gitlab_should_be_two(self):
        assert self.stats.mrs_in_gitlab == 2
