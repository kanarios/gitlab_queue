"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import PipelineAttributes


class Scenario(vedro.Scenario):
    subject = "create pipeline attributes"

    def when_pipeline_attributes_are_created(self):
        self.attrs = PipelineAttributes(
            id=456,
            status="success",
            sha="abc123",
            ref="master",
            web_url="https://gitlab.com/pipeline/456",
        )

    def then_it_should_have_correct_fields(self):
        assert self.attrs.id == 456
        assert self.attrs.status == "success"
        assert self.attrs.sha == "abc123"
        assert self.attrs.ref == "master"
        assert self.attrs.web_url == "https://gitlab.com/pipeline/456"
