"""Test scenario: get_latest_mr_pipeline returns None when no pipelines."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_mr_pipelines


class Scenario(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns None when no pipelines"

    async def given_mock_gitlab_without_pipelines(self):
        self._mock_ctx = mocked_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, [])
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_latest_mr_pipeline_is_called(self):
        self.result = await self.client.get_latest_mr_pipeline(42)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
