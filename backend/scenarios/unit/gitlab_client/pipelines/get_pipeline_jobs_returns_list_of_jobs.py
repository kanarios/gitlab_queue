"""Test scenario: get_pipeline_jobs returns list of jobs."""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_job_response


class Scenario(vedro.Scenario):
    subject = "get_pipeline_jobs returns list of jobs"

    def given_mock_gitlab_with_jobs(self):
        self.jobs_data = [
            create_job_response(1, name="lint", status="success", stage="lint"),
            create_job_response(2, name="test", status="success", stage="test"),
            create_job_response(3, name="build", status="failed", stage="build"),
        ]
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/pipelines/456/jobs",
            json_data=self.jobs_data,
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_pipeline_jobs_is_called(self):
        self.result = await self.client.get_pipeline_jobs(456)

    def then_result_should_have_three_jobs(self):
        assert len(self.result) == 3

    def and_job_fields_should_be_parsed(self):
        job = self.result[0]
        assert job.id == 1
        assert job.name == "lint"
        assert job.status == "success"
        assert job.stage == "lint"

    def and_failed_job_should_be_included(self):
        failed_job = next(j for j in self.result if j.status == "failed")
        assert failed_job.name == "build"

    async def do_cleanup(self):
        if hasattr(self, "client"):
            await self.client.close()
