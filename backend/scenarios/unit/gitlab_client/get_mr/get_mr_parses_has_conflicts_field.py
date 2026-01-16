"""Test scenario: get_mr parses has_conflicts field."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_mr

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr parses has_conflicts field"

    async def given_mock_gitlab_with_conflicting_mr(self):
        self.mr_data = create_mr_api_response(
            iid=50,
            has_conflicts=True,
            merge_status="cannot_be_merged",
        )
        self._mock_ctx = mocked_gitlab_get_mr(TEST_PROJECT_ID, 50, self.mr_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(50)

    def then_has_conflicts_should_be_true(self):
        assert self.result.has_conflicts is True

    def and_merge_status_should_be_cannot_be_merged(self):
        assert self.result.merge_status == "cannot_be_merged"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
