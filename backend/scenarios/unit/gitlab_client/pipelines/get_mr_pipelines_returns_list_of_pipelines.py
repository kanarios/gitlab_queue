"""Test scenario: get_mr_pipelines returns list of pipelines."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_mr_pipelines

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_mr_pipelines returns list of pipelines"

    async def given_mock_gitlab_with_pipelines(self):
        self.pipelines_data = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
            create_pipeline_response(98, status="canceled"),
        ]
        self._mock_ctx = mocked_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, self.pipelines_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_pipelines_is_called(self):
        self.result = await self.client.get_mr_pipelines(42)

    def then_result_should_have_three_pipelines(self):
        assert len(self.result) == 3

    def and_first_pipeline_should_be_newest(self):
        assert self.result[0].id == 100
        assert self.result[0].status == "success"

    def and_pipeline_fields_should_be_parsed(self):
        pipeline = self.result[0]
        assert pipeline.sha == "abc123"
        assert pipeline.ref == "feature-branch"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
