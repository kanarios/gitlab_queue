"""Test check_needs_rebase returns NEEDS_REBASE for various merge statuses."""

import vedro
from vedro import params

from gitlab_queue.core.rebase_during_testing import MergeReadiness

from ..._helpers import MockMergeRequest, create_handler, create_mock_gitlab_client


class Scenario(vedro.Scenario):
    subject = "check_needs_rebase returns NEEDS_REBASE for merge_status='{merge_status}'"

    @params("cannot_be_merged")
    @params("cannot_be_merged_recheck")
    @params("unchecked")
    def __init__(self, merge_status: str):
        self.merge_status = merge_status

    def given_handler_with_non_mergeable_mr(self):
        mr = MockMergeRequest(
            merge_status=self.merge_status,
            has_conflicts=False,
        )
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)

    async def when_check_needs_rebase_is_called(self):
        self.result = await self.handler.check_needs_rebase(42)

    def then_result_is_needs_rebase(self):
        assert self.result == MergeReadiness.NEEDS_REBASE
