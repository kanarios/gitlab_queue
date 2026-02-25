"""Test merge_mr succeeds when merge_status is 'can_be_merged'."""

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import _mr_to_dict, create_gitlab_client_for_test, create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr succeeds when merge_status is 'can_be_merged'"

    def given_mr_ready_to_merge(self):
        self.mr = create_mr(merge_status="can_be_merged")
        self.iid = 42

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
        ):
            mock_get_mr.return_value = self.mr
            mock_put.return_value = _mr_to_dict("merged")

            client = create_gitlab_client_for_test()
            self.result = await client.merge_mr(self.iid)
            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_mr_called_once(self):
        """
        Asserts that the mocked GitLabClient.get_mr method was invoked exactly once during the scenario.
        
        Raises:
            AssertionError: If the mock's call count is not 1.
        """
        assert self.mock_get_mr.call_count == 1

    def and_put_called_with_merge_endpoint(self):
        """
        Verify the GitLab client's PUT was awaited once and targeted the merge endpoint for the MR with iid 42.
        
        Raises:
        	AssertionError: If the PUT was not awaited exactly once or if the request URL does not include '/merge_requests/42/merge'.
        """
        self.mock_put.assert_awaited_once()
        call_args = self.mock_put.call_args
        assert "/merge_requests/42/merge" in call_args.args[0]
