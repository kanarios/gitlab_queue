"""Test job retry finds all failed jobs among many jobs.

Regression test for MR 5100 / pipeline #2857349 (~30 jobs).
When a pipeline has >20 jobs, all failed jobs must be found and retried,
not just those on the first page of the API response.

FakeGitLabClient always returns the full list — this test documents the
requirement at the handler level and guards against regression.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)

FAILED_JOB_IDS = [21, 22, 23, 24, 25]


class Scenario(vedro.Scenario):
    subject = "job retry finds all failed jobs among 25 jobs (regression for >20 jobs pipelines)"

    def given_processor_with_25_jobs_including_5_failed(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        jobs = []
        for i in range(1, 16):
            jobs.append(create_job(id=i, name=f"job-{i}", status="success"))
        for i in range(16, 21):
            jobs.append(create_job(id=i, name=f"manual-{i}", status="manual"))
        for i in FAILED_JOB_IDS:
            jobs.append(create_job(id=i, name=f"e2e-tests {i - 20}/5", status="failed"))

        self.processor.gitlab_client.pipeline_jobs_response = jobs

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.retried_jobs: dict[str, int] = {}

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs,
        )

    def then_should_continue_is_true(self):
        assert self.should_continue is True

    def and_all_five_failed_jobs_were_retried(self):
        assert sorted(self.processor.gitlab_client.retry_job_calls) == sorted(FAILED_JOB_IDS)

    def and_retried_jobs_tracks_all_five(self):
        for i in FAILED_JOB_IDS:
            job_name = f"e2e-tests {i - 20}/5"
            assert self.updated_retried.get(job_name) == 1, f"Missing retry for {job_name}"
