"""Test check_needs_rebase returns READY for merge_status='can_be_merged'."""

import vedro

from gitlab_queue.core.rebase_during_testing import MergeReadiness

from ..._helpers import MockMergeRequest, create_handler, create_mock_gitlab_client


class Scenario(vedro.Scenario):
    subject = "check_needs_rebase returns READY for merge_status='can_be_merged'"

    def given_handler_with_can_be_merged_mr(self):
        mr = MockMergeRequest(merge_status="can_be_merged", has_conflicts=False)
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)

    async def when_check_needs_rebase_is_called(self):
        self.result = await self.handler.check_needs_rebase(42)

    def then_result_is_ready(self):
        assert self.result == MergeReadiness.READY
