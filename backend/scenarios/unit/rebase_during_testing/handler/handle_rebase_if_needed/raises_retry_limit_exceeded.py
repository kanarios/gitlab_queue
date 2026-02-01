"""Test handle_rebase_if_needed raises RebaseRetryLimitExceeded when max_attempts reached."""

import vedro
from vedro import catched

from gitlab_queue.core.rebase_during_testing import RebaseRetryLimitExceeded

from ..._helpers import (
    MockMergeRequest,
    create_context,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed raises RebaseRetryLimitExceeded when max_attempts reached"

    def given_handler_with_needs_rebase_and_exhausted_attempts(self):
        mr = MockMergeRequest(merge_status="cannot_be_merged", has_conflicts=False)
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)
        self.ctx = create_context(rebase_count=3, max_attempts=3)

    async def when_handle_rebase_if_needed_is_called(self):
        with catched(RebaseRetryLimitExceeded) as self.exception:
            await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_rebase_retry_limit_exceeded_is_raised(self):
        assert self.exception.type is RebaseRetryLimitExceeded

    def and_error_message_contains_mr_iid(self):
        assert "42" in str(self.exception.value)
