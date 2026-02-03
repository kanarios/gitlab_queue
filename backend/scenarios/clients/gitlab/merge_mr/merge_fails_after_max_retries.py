"""Test merge_mr fails after max retries when status stays 'checking'."""

from unittest.mock import AsyncMock, patch

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabClient, GitLabConflictError

from ._helpers import create_mr


class Scenario(vedro.Scenario):
    subject = "merge_mr fails after max retries when status stays 'checking'"

    def given_mr_always_checking(self):
        self.checking_mr = create_mr(merge_status="checking")
        self.iid = 42

    async def when_merge_mr_is_called(self):
        with (
            patch.object(GitLabClient, "get_mr", new_callable=AsyncMock) as mock_get_mr,
            patch.object(GitLabClient, "put", new_callable=AsyncMock) as mock_put,
            patch.object(GitLabClient, "__init__", lambda self, *args, **kwargs: None),
            patch("gitlab_queue.clients.gitlab.asyncio.sleep", new_callable=AsyncMock),
        ):
            # Always return 'checking' - will timeout after max_retries (10)
            mock_get_mr.return_value = self.checking_mr

            client = GitLabClient.__new__(GitLabClient)
            with catched(GitLabConflictError) as self.exception:
                await client.merge_mr(self.iid)

            self.mock_get_mr = mock_get_mr
            self.mock_put = mock_put

    def then_conflict_error_is_raised(self):
        assert self.exception.type is GitLabConflictError

    def and_error_message_contains_timeout(self):
        assert "timeout" in str(self.exception.value).lower()

    def and_get_mr_called_ten_times(self):
        assert self.mock_get_mr.call_count == 10

    def and_put_never_called(self):
        self.mock_put.assert_not_called()
