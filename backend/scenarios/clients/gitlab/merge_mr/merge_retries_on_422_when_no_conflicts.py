"""Test merge_mr retries on HTTP 422 when has_conflicts=False, then succeeds."""

from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabClient

from ._helpers import _mr_to_dict, create_gitlab_client_for_test, create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr retries on HTTP 422 when has_conflicts=False, then succeeds"

    def given_mr_ready_but_api_returns_422_initially(self):
        self.mr = create_mr(merge_status="can_be_merged", has_conflicts=False)
        self.iid = 42
        self.api_error = GitLabAPIError("Branch cannot be merged", status_code=422)

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
            patch("gitlab_queue.clients.gitlab.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_get_mr.return_value = self.mr
            # First put() raises 422, second succeeds
            mock_put.side_effect = [
                self.api_error,
                _mr_to_dict("merged"),
            ]

            client = create_gitlab_client_for_test()
            self.result = await client.merge_mr(self.iid)
            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_mr_called_twice(self):
        assert self.mock_get_mr.call_count == 2

    def and_put_called_twice(self):
        assert self.mock_put.call_count == 2
