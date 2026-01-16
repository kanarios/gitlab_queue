"""Unit tests for Pipeline and Job models."""

import vedro

from gitlab_queue.models.pipeline import Pipeline


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
