"""Test: _verify_mr_in_queue returns False for MR without any trigger label."""

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.processor import MergeProcessor
from scenarios.library import Labels


class Scenario(vedro.Scenario):
    subject = "verify mr in queue returns false without any trigger label"

    def given_processor(self):
        self.settings = MagicMock()
        self.settings.queue_label = Labels.MERGE_QUEUE
        self.settings.hotfix_label = Labels.HOTFIX

        self.gitlab_client = MagicMock()
        mr_mock = MagicMock()
        mr_mock.state = "opened"
        mr_mock.labels = ["feature"]  # Neither queue nor hotfix
        self.gitlab_client.get_mr = AsyncMock(return_value=mr_mock)

        self.queue_manager = MagicMock()
        self.notifier = MagicMock()

        self.processor = MergeProcessor(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            notifier=self.notifier,
            settings=self.settings,
        )

    async def when_verify_is_called(self):
        self.result = await self.processor._verify_mr_in_queue(42)

    def then_result_should_be_false(self):
        assert self.result is False
