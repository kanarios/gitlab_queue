"""Test scenario: list_mrs_with_label returns empty list when no MRs."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_list_mrs


class Scenario(vedro.Scenario):
    subject = "list_mrs_with_label returns empty list when no MRs"

    async def given_mock_gitlab_with_no_mrs(self):
        self._mock_ctx = mocked_gitlab_list_mrs(TEST_PROJECT_ID, [], label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_result_should_be_empty_list(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
