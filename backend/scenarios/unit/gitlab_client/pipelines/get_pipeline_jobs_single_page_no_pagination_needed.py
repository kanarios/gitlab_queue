"""Test scenario: get_pipeline_jobs returns all jobs when only one page exists."""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_pipeline_jobs returns all jobs without pagination when single page"

    def given_mock_gitlab_with_single_page_of_jobs(self):
        self.jobs_data = [
            create_job_response(1, name="lint", status="success"),
            create_job_response(2, name="test", status="success"),
            create_job_response(3, name="build", status="failed"),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/456/jobs",
            json_data=self.jobs_data,
            headers={"x-next-page": ""},
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_pipeline_jobs_is_called(self):
        self.result = await self.client.get_pipeline_jobs(456)

    def then_all_three_jobs_are_returned(self):
        assert len(self.result) == 3

    def and_transport_received_one_request(self):
        assert self.transport.call_count == 1

    async def do_cleanup(self):
        await self.client.close()
