"""Test scenario: list_mrs_with_label returns multiple MRs."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_list_mrs

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "list_mrs_with_label returns multiple MRs"

    async def given_mock_gitlab_with_multiple_mrs(self):
        self.mrs_data = [
            create_mr_api_response(iid=1, title="First MR"),
            create_mr_api_response(iid=2, title="Second MR"),
            create_mr_api_response(iid=3, title="Third MR"),
        ]
        self._mock_ctx = mocked_gitlab_list_mrs(TEST_PROJECT_ID, self.mrs_data, label="merge_queue")
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_list_mrs_is_called(self):
        self.result = await self.client.list_mrs_with_label("merge_queue")

    def then_result_should_have_three_mrs(self):
        assert len(self.result) == 3

    def and_first_mr_should_have_correct_iid(self):
        assert self.result[0].iid == 1

    def and_second_mr_should_have_correct_iid(self):
        assert self.result[1].iid == 2

    def and_third_mr_should_have_correct_iid(self):
        assert self.result[2].iid == 3

    def and_titles_should_match(self):
        assert self.result[0].title == "First MR"
        assert self.result[1].title == "Second MR"
        assert self.result[2].title == "Third MR"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
