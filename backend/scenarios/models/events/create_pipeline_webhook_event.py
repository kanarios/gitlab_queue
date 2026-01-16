"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import PipelineAttributes, PipelineEvent


class Scenario(vedro.Scenario):
    subject = "create pipeline webhook event"

    def given_pipeline_event_data(self):
        self.attrs = PipelineAttributes(
            id=789,
            status="success",
            sha="def456",
            ref="master",
        )

    def when_pipeline_event_is_created(self):
        self.event = PipelineEvent(
            object_kind="pipeline",
            project_id=42,
            object_attributes=self.attrs,
            merge_request_iid=123,
        )

    def then_it_should_have_correct_fields(self):
        assert self.event.object_kind == "pipeline"
        assert self.event.project_id == 42
        assert self.event.object_attributes == self.attrs
        assert self.event.merge_request_iid == 123
