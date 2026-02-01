"""Test check_needs_rebase returns HAS_CONFLICTS when has_conflicts=True."""

import vedro

from gitlab_queue.core.rebase_during_testing import MergeReadiness

from ..._helpers import MockMergeRequest, create_handler, create_mock_gitlab_client


class Scenario(vedro.Scenario):
    subject = "check_needs_rebase returns HAS_CONFLICTS when has_conflicts=True"

    def given_handler_with_conflicting_mr(self):
        mr = MockMergeRequest(has_conflicts=True)
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)

    async def when_check_needs_rebase_is_called(self):
        self.result = await self.handler.check_needs_rebase(42)

    def then_result_is_has_conflicts(self):
        assert self.result == MergeReadiness.HAS_CONFLICTS
