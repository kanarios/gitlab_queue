"""Test scenario: merge_mr returns MR with merged state."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr, mocked_gitlab_merge

from ._helpers import create_mr_response


class Scenario(vedro.Scenario):
    subject = "merge_mr returns MR with merged state"

    async def given_mock_gitlab_for_successful_merge(self):
        # Check merge status
        mr_data = create_mr_response(iid=99, merge_status="can_be_merged")
        self._get_mock = mocked_gitlab_get_mr(TEST_PROJECT_ID, 99, mr_data)
        await self._get_mock.__aenter__()

        # Merge returns merged MR
        merged_data = create_mr_response(
            iid=99,
            state="merged",
            merge_status="merged",
        )
        self._merge_mock = mocked_gitlab_merge(TEST_PROJECT_ID, 99, success=True, merged_data=merged_data)
        await self._merge_mock.__aenter__()
        self.client = create_test_client()

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(99)

    def then_iid_should_match(self):
        assert self.result.iid == 99

    def and_state_should_be_merged(self):
        assert self.result.state == "merged"

    def and_merge_status_should_be_merged(self):
        assert self.result.merge_status == "merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._merge_mock.__aexit__(None, None, None)
        await self._get_mock.__aexit__(None, None, None)
