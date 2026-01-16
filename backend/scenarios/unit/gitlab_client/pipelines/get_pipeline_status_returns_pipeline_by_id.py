"""Test scenario: get_pipeline_status returns pipeline by ID."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import mocked_gitlab_pipeline

from ._helpers import create_pipeline_response


class Scenario(vedro.Scenario):
    subject = "get_pipeline_status returns pipeline by ID"

    async def given_mock_gitlab_with_pipeline(self):
        self.pipeline_data = create_pipeline_response(
            456,
            status="running",
            sha="running123",
            ref="main",
        )
        self._mock_ctx = mocked_gitlab_pipeline(TEST_PROJECT_ID, 456, self.pipeline_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_pipeline_status_is_called(self):
        self.result = await self.client.get_pipeline_status(456)

    def then_pipeline_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 456

    def and_status_should_be_running(self):
        assert self.result.status == "running"

    def and_sha_should_match(self):
        assert self.result.sha == "running123"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
