"""Test scenario: merge_mr raises GitLabConflictError when MR is not mergeable."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr

from gitlab_queue.clients.gitlab import GitLabConflictError

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "try to merge mr when mr is not mergeable"

    async def given_mock_gitlab_with_unmergeable_mr(self):
        # MR has conflicts - cannot be merged
        mr_data = create_mr_response(
            iid=42,
            merge_status="cannot_be_merged",
            has_conflicts=True,
        )
        self._get_mock = mocked_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._get_mock.__aenter__()
        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.error = None
        try:
            await self.client.merge_mr(42)
        except GitLabConflictError as e:
            self.error = e

    def then_error_should_be_raised(self):
        assert self.error is not None

    def and_error_should_be_conflict_error(self):
        assert isinstance(self.error, GitLabConflictError)

    def and_error_message_should_mention_status(self):
        assert "cannot_be_merged" in str(self.error)

    async def do_cleanup(self):
        await self.client.close()
        await self._get_mock.__aexit__(None, None, None)
