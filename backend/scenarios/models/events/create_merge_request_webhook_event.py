"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
)


class Scenario(vedro.Scenario):
    subject = "create merge request webhook event"

    def given_mr_event_data(self):
        self.attrs = MergeRequestAttributes(
            iid=123,
            title="Test MR",
            state="opened",
            action="labeled",
            source_branch="feature",
            target_branch="master",
            merge_status="can_be_merged",
        )
        self.label_changes = LabelChanges(
            previous=[],
            current=["merge_queue"],
        )

    def when_mr_event_is_created(self):
        self.event = MergeRequestEvent(
            object_kind="merge_request",
            event_type="merge_request",
            project_id=42,
            object_attributes=self.attrs,
            user_id=1,
            user_name="John Doe",
            user_username="johndoe",
            labels=["merge_queue"],
            label_changes=self.label_changes,
        )

    def then_it_should_have_correct_fields(self):
        assert self.event.object_kind == "merge_request"
        assert self.event.project_id == 42
        assert self.event.object_attributes == self.attrs
        assert self.event.labels == ["merge_queue"]
        assert self.event.label_changes == self.label_changes
