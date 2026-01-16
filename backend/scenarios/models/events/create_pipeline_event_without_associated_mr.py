"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import PipelineAttributes, PipelineEvent


class Scenario(vedro.Scenario):
    subject = "create pipeline event without associated MR"

    def given_pipeline_attrs(self):
        self.attrs = PipelineAttributes(
            id=999,
            status="running",
            sha="ghi789",
            ref="feature-branch",
        )

    def when_pipeline_event_is_created_without_mr(self):
        self.event = PipelineEvent(
            object_kind="pipeline",
            project_id=42,
            object_attributes=self.attrs,
        )

    def then_mr_iid_should_be_none(self):
        assert self.event.merge_request_iid is None
