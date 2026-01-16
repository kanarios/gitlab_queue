"""Test scenario: get_mr_conflicts uses old_path when new_path is missing."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_get_conflicts


class Scenario(vedro.Scenario):
    subject = "get_mr_conflicts uses old_path when new_path is missing"

    async def given_mock_gitlab_with_old_path_only(self):
        self.conflicts_data = [
            {"old_path": "legacy.py"},  # No new_path
        ]
        self._mock_ctx = mocked_gitlab_get_conflicts(TEST_PROJECT_ID, 42, self.conflicts_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_conflicts_is_called(self):
        self.result = await self.client.get_mr_conflicts(42)

    def then_result_should_contain_old_path(self):
        assert self.result == ["legacy.py"]

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
