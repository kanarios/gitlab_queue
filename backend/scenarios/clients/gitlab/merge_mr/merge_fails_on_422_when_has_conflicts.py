"""Test merge_mr fails immediately on HTTP 422 when has_conflicts=True."""

from unittest.mock import AsyncMock, patch

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabClient

from ._helpers import create_gitlab_client_for_test, create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr fails immediately on HTTP 422 when has_conflicts=True"

    def given_mr_with_conflicts_and_api_returns_422(self):
        self.mr = create_mr(merge_status="can_be_merged", has_conflicts=True)
        self.iid = 42
        self.api_error = GitLabAPIError("Branch cannot be merged", status_code=422)

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
        ):
            mock_get_mr.return_value = self.mr
            mock_put.side_effect = self.api_error

            client = create_gitlab_client_for_test()
            with catched(GitLabAPIError) as self.exception:
                await client.merge_mr(self.iid)

            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_api_error_is_raised(self):
        assert self.exception.type is GitLabAPIError

    def and_error_has_status_422(self):
        assert self.exception.value.status_code == 422

    def and_get_mr_called_once(self):
        assert self.mock_get_mr.call_count == 1

    def and_put_called_once(self):
        assert self.mock_put.call_count == 1
