"""Unit tests for Pipeline and Job models."""

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.pipeline import Pipeline


class Scenario(vedro.Scenario):
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
