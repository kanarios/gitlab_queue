"""Test merge_mr fails immediately when merge_status is 'cannot_be_merged'."""

from unittest.mock import AsyncMock, patch

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabClient, GitLabConflictError

from ._helpers import create_gitlab_client_for_test, create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr fails immediately when merge_status is 'cannot_be_merged'"

    def given_mr_cannot_be_merged(self):
        self.mr = create_mr(merge_status="cannot_be_merged", has_conflicts=True)
        self.iid = 42

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
        ):
            mock_get_mr.return_value = self.mr

            client = create_gitlab_client_for_test()
            with catched(GitLabConflictError) as self.exception:
                await client.merge_mr(self.iid)

            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_conflict_error_is_raised(self):
        assert self.exception.type is GitLabConflictError

    def and_error_message_contains_status(self):
        assert "cannot_be_merged" in str(self.exception.value)

    def and_get_mr_called_once(self):
        """
        Assert that GitLabClient.get_mr was called exactly once.
        
        Raises:
            AssertionError: If `self.mock_get_mr.call_count` is not 1.
        """
        assert self.mock_get_mr.call_count == 1

    def and_put_never_awaited(self):
        """
        Asserts that the mocked GitLabClient.put coroutine was never awaited during the scenario.
        
        This verifies that no asynchronous PUT operation was executed after attempting to merge the merge request.
        """
        self.mock_put.assert_not_awaited()
