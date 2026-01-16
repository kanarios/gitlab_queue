"""Test scenario: get_latest_mr_pipeline returns first (newest) pipeline."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_mr_pipelines

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns first (newest) pipeline"

    async def given_mock_gitlab_with_multiple_pipelines(self):
        self.pipelines_data = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
        ]
        self._mock_ctx = mocked_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, self.pipelines_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_latest_mr_pipeline_is_called(self):
        self.result = await self.client.get_latest_mr_pipeline(42)

    def then_result_should_be_first_pipeline(self):
        assert self.result is not None
        assert self.result.id == 100

    def and_status_should_be_success(self):
        assert self.result.status == "success"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
