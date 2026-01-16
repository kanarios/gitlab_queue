"""Test scenario: merge_mr merges MR successfully."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr, mocked_gitlab_merge

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "merge_mr merges MR successfully"

    async def given_mock_gitlab_with_mergeable_mr(self):
        # First call: get_mr to check merge_status
        mr_data = create_mr_response(iid=42, merge_status="can_be_merged")
        self._get_mock = mocked_gitlab_get_mr(TEST_PROJECT_ID, 42, mr_data)
        await self._get_mock.__aenter__()

        # Second call: merge endpoint
        merged_data = create_mr_response(iid=42, state="merged", merge_status="merged")
        self._merge_mock = mocked_gitlab_merge(TEST_PROJECT_ID, 42, success=True, merged_data=merged_data)
        await self._merge_mock.__aenter__()

        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(42)

    def then_result_should_be_merged_mr(self):
        assert self.result is not None
        assert self.result.iid == 42

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._merge_mock.__aexit__(None, None, None)
        await self._get_mock.__aexit__(None, None, None)
