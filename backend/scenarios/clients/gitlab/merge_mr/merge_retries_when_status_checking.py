"""Test merge_mr retries when merge_status is 'checking', then succeeds."""

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabClient

from ._helpers import _mr_to_dict, create_gitlab_client_for_test, create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr retries when merge_status is 'checking', then succeeds"

    def given_mr_checking_then_ready(self):
        self.checking_mr = create_mr(merge_status="checking")
        self.ready_mr = create_mr(merge_status="can_be_merged")
        self.iid = 42

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
            patch("gitlab_queue.clients.gitlab.asyncio.sleep", new_callable=AsyncMock),
        ):
            # Return 'checking' twice, then 'can_be_merged'
            mock_get_mr.side_effect = [
                self.checking_mr,
                self.checking_mr,
                self.ready_mr,
            ]
            mock_put.return_value = _mr_to_dict("merged")

            client = create_gitlab_client_for_test()
            self.result = await client.merge_mr(self.iid)
            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_mr_called_three_times(self):
        assert self.mock_get_mr.call_count == 3

    def and_put_called_once(self):
        self.mock_put.assert_awaited_once()
