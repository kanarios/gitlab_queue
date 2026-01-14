"""Test scenarios for GitLabClient pipeline operations.

Tests pipeline-related methods including:
- get_mr_pipelines()
- get_latest_mr_pipeline()
- get_pipeline_status()
- get_pipeline_jobs()
- retry_pipeline_job()
"""

from __future__ import annotations

import vedro
from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, create_test_client
from scenarios.contexts.jj_gitlab_mock import (
    mock_gitlab_mr_pipelines,
    mock_gitlab_pipeline,
    mock_gitlab_pipeline_jobs,
    mock_gitlab_retry_job,
)


def create_pipeline_response(
    pipeline_id: int,
    status: str = "success",
    sha: str = "abc123",
    ref: str = "feature-branch",
) -> dict:
    """Create a GitLab pipeline API response for testing."""
    return {
        "id": pipeline_id,
        "status": status,
        "sha": sha,
        "ref": ref,
        "web_url": f"https://gitlab.com/project/-/pipelines/{pipeline_id}",
        "created_at": "2024-01-15T10:30:00Z",
    }


def create_job_response(
    job_id: int,
    name: str = "test",
    status: str = "success",
    stage: str = "test",
) -> dict:
    """Create a GitLab job API response for testing."""
    return {
        "id": job_id,
        "name": name,
        "status": status,
        "stage": stage,
        "web_url": f"https://gitlab.com/project/-/jobs/{job_id}",
    }


class Scenario__get_mr_pipelines_returns_list(vedro.Scenario):
    subject = "get_mr_pipelines returns list of pipelines"

    async def given_mock_gitlab_with_pipelines(self):
        self.pipelines_data = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
            create_pipeline_response(98, status="canceled"),
        ]
        self._mock_ctx = mock_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, self.pipelines_data)
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


class Scenario__get_mr_pipelines_returns_empty_list(vedro.Scenario):
    subject = "get_mr_pipelines returns empty list when no pipelines"

    async def given_mock_gitlab_without_pipelines(self):
        self._mock_ctx = mock_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, [])
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_mr_pipelines_is_called(self):
        self.result = await self.client.get_mr_pipelines(42)

    def then_result_should_be_empty(self):
        assert self.result == []

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_latest_mr_pipeline_returns_first(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns first (newest) pipeline"

    async def given_mock_gitlab_with_multiple_pipelines(self):
        self.pipelines_data = [
            create_pipeline_response(100, status="success"),
            create_pipeline_response(99, status="failed"),
        ]
        self._mock_ctx = mock_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, self.pipelines_data)
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


class Scenario__get_latest_mr_pipeline_returns_none_when_empty(vedro.Scenario):
    subject = "get_latest_mr_pipeline returns None when no pipelines"

    async def given_mock_gitlab_without_pipelines(self):
        self._mock_ctx = mock_gitlab_mr_pipelines(TEST_PROJECT_ID, 42, [])
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_get_latest_mr_pipeline_is_called(self):
        self.result = await self.client.get_latest_mr_pipeline(42)

    def then_result_should_be_none(self):
        assert self.result is None

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__get_pipeline_status_returns_pipeline(vedro.Scenario):
    subject = "get_pipeline_status returns pipeline by ID"

    async def given_mock_gitlab_with_pipeline(self):
        self.pipeline_data = create_pipeline_response(
            456,
            status="running",
            sha="running123",
            ref="main",
        )
        self._mock_ctx = mock_gitlab_pipeline(TEST_PROJECT_ID, 456, self.pipeline_data)
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


class Scenario__get_pipeline_jobs_returns_list(vedro.Scenario):
    subject = "get_pipeline_jobs returns list of jobs"

    async def given_mock_gitlab_with_jobs(self):
        self.jobs_data = [
            create_job_response(1, name="lint", status="success", stage="lint"),
            create_job_response(2, name="test", status="success", stage="test"),
            create_job_response(3, name="build", status="failed", stage="build"),
        ]
        self._mock_ctx = mock_gitlab_pipeline_jobs(TEST_PROJECT_ID, 456, self.jobs_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

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
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)


class Scenario__retry_pipeline_job_retries_job(vedro.Scenario):
    subject = "retry_pipeline_job retries a failed job"

    async def given_mock_gitlab_for_retry(self):
        self.job_data = create_job_response(
            789,
            name="test",
            status="pending",  # After retry, status becomes pending
            stage="test",
        )
        self._mock_ctx = mock_gitlab_retry_job(TEST_PROJECT_ID, 789, self.job_data)
        await self._mock_ctx.__aenter__()
        self.client = create_test_client()

    async def when_retry_pipeline_job_is_called(self):
        self.result = await self.client.retry_pipeline_job(789)

    def then_job_should_be_returned(self):
        assert self.result is not None
        assert self.result.id == 789

    def and_status_should_be_pending(self):
        assert self.result.status == "pending"

    async def do_cleanup(self):
        await self.client.close()
        await self._mock_ctx.__aexit__(None, None, None)
