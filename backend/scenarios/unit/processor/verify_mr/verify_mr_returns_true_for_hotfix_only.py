"""Test: _verify_mr_in_queue returns True for MR with only hotfix label."""

import vedro

from gitlab_queue.core.processor import MergeProcessor
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeQueueManager, FakeSettings, create_mr
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "verify mr in queue returns true for MR with only hotfix label"

    def given_opened_hotfix_mr_without_queue_label(self):
        self.settings = FakeSettings(
            queue_label=Labels.MERGE_QUEUE,
            hotfix_label=Labels.HOTFIX,
        )

        self.gitlab_client = FakeGitLabClient(
            mr_responses={
                42: create_mr(iid=42, state="opened", labels=[Labels.HOTFIX]),
            },
        )

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=FakeQueueManager(),
            notifier=FakeNotifier(),
            settings=self.settings,
        )

    async def when_verify_is_called(self):
        self.result = await self.processor._verify_mr_in_queue(42)

    def then_result_should_be_true(self):
        assert self.result is True
