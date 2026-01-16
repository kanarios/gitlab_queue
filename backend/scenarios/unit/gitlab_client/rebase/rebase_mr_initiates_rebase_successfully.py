"""Test scenario: rebase_mr initiates rebase successfully."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_rebase


class Scenario(vedro.Scenario):
    subject = "rebase_mr initiates rebase successfully"

    async def given_mock_gitlab_for_rebase(self):
        self._mock_ctx = mocked_gitlab_rebase(TEST_PROJECT_ID, 42, success=True)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_rebase_mr_is_called(self):
        self.result = await self.client.rebase_mr(42)

    def then_result_should_be_true(self):
        assert self.result is True

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
