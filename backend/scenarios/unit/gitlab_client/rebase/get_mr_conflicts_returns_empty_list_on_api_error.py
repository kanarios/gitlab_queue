"""Test scenario: get_mr_conflicts returns empty list on API error."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_conflicts


class Scenario(vedro.Scenario):
    subject = "get_mr_conflicts returns empty list on API error"

    async def given_mock_gitlab_returns_404(self):
        self._mock_ctx = mocked_gitlab_get_conflicts(TEST_PROJECT_ID, 42, {"message": "Not Found"}, status=404)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_conflicts_is_called(self):
        # Should not raise, returns empty list as fallback
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_be_empty(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
