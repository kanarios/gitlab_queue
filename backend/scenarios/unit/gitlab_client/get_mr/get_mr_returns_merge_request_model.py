"""Test scenario: get_mr returns MergeRequest model."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr returns MergeRequest model"

    async def given_mock_gitlab_with_mr(self):
        self.mr_data = create_mr_api_response(iid=42, title="Test MR")
        self._mock_ctx = mocked_gitlab_get_mr(TEST_PROJECT_ID, 42, self.mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(42)

    def then_result_should_be_merge_request(self):
        assert self.result is not None

    def and_iid_should_match(self):
        assert self.result.iid == 42

    def and_title_should_match(self):
        assert self.result.title == "Test MR"

    def and_state_should_match(self):
        assert self.result.state == "opened"

    def and_author_should_be_parsed(self):
        assert self.result.author.id == 1
        assert self.result.author.name == "Test User"
        assert self.result.author.username == "testuser"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
