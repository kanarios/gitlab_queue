"""Unit tests for Pipeline and Job models."""

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.pipeline import Job, Pipeline


class Scenario(vedro.Scenario):
    subject = "create pipeline with required fields"

    def given_pipeline_data(self):
        self.pipeline_id = 12345
        self.status = "running"
        self.sha = "abc123def456"
        self.ref = "master"

    def when_pipeline_is_created(self):
        self.pipeline = Pipeline(
            id=self.pipeline_id,
            status=self.status,
            sha=self.sha,
            ref=self.ref,
        )

    def then_it_should_have_correct_required_fields(self):
        assert self.pipeline.id == self.pipeline_id
        assert self.pipeline.status == self.status
        assert self.pipeline.sha == self.sha
        assert self.pipeline.ref == self.ref

    def and_it_should_have_none_for_optional_fields(self):
        assert self.pipeline.web_url is None
        assert self.pipeline.created_at is None


class Scenario__create_pipeline_with_all_fields(vedro.Scenario):
    subject = "create pipeline with all optional fields"

    def given_full_pipeline_data(self):
        self.created_at = datetime.now(UTC)

    def when_pipeline_is_created_with_all_fields(self):
        self.pipeline = Pipeline(
            id=67890,
            status="success",
            sha="def789ghi012",
            ref="feature-branch",
            web_url="https://gitlab.com/project/-/pipelines/67890",
            created_at=self.created_at,
        )

    def then_it_should_have_all_fields_set(self):
        assert self.pipeline.id == 67890
        assert self.pipeline.status == "success"
        assert self.pipeline.web_url == "https://gitlab.com/project/-/pipelines/67890"
        assert self.pipeline.created_at == self.created_at


class Scenario__pipeline_is_frozen(vedro.Scenario):
    subject = "pipeline is immutable (frozen)"

    def given_pipeline(self):
        self.pipeline = Pipeline(id=1, status="pending", sha="abc", ref="master")

    def when_trying_to_modify_pipeline(self):
        try:
            self.pipeline.status = "success"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None


class Scenario__pipeline_statuses(vedro.Scenario):
    subject = "pipeline can have various statuses"

    def given_valid_statuses(self):
        self.statuses = ["pending", "running", "success", "failed", "canceled"]

    def when_pipelines_are_created_with_each_status(self):
        self.pipelines = [
            Pipeline(id=i, status=status, sha=f"sha{i}", ref="master")
            for i, status in enumerate(self.statuses)
        ]

    def then_all_pipelines_should_have_correct_status(self):
        for pipeline, expected_status in zip(self.pipelines, self.statuses, strict=False):
            assert pipeline.status == expected_status


class Scenario__create_job(vedro.Scenario):
    subject = "create job with required fields"

    def given_job_data(self):
        self.job_id = 999
        self.name = "test"
        self.status = "success"
        self.stage = "test"

    def when_job_is_created(self):
        self.job = Job(
            id=self.job_id,
            name=self.name,
            status=self.status,
            stage=self.stage,
        )

    def then_it_should_have_correct_fields(self):
        assert self.job.id == self.job_id
        assert self.job.name == self.name
        assert self.job.status == self.status
        assert self.job.stage == self.stage
        assert self.job.web_url is None


class Scenario__create_job_with_web_url(vedro.Scenario):
    subject = "create job with web URL"

    def when_job_is_created_with_url(self):
        self.job = Job(
            id=1000,
            name="build",
            status="running",
            stage="build",
            web_url="https://gitlab.com/project/-/jobs/1000",
        )

    def then_it_should_have_web_url(self):
        assert self.job.web_url == "https://gitlab.com/project/-/jobs/1000"


class Scenario__job_is_frozen(vedro.Scenario):
    subject = "job is immutable (frozen)"

    def given_job(self):
        self.job = Job(id=1, name="test", status="pending", stage="test")

    def when_trying_to_modify_job(self):
        try:
            self.job.status = "success"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None
