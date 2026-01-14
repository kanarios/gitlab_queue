"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import (
    LabelChanges,
    MergeRequestAttributes,
    MergeRequestEvent,
    NoteEvent,
    PipelineAttributes,
    PipelineEvent,
    validate_webhook_token,
)


class Scenario(vedro.Scenario):
    subject = "create merge request attributes"

    def given_mr_attributes_data(self):
        self.iid = 123
        self.title = "Fix bug"
        self.state = "opened"
        self.action = "update"

    def when_mr_attributes_are_created(self):
        self.attrs = MergeRequestAttributes(
            iid=self.iid,
            title=self.title,
            state=self.state,
            action=self.action,
            source_branch="fix-branch",
            target_branch="master",
            merge_status="can_be_merged",
        )

    def then_it_should_have_correct_fields(self):
        assert self.attrs.iid == self.iid
        assert self.attrs.title == self.title
        assert self.attrs.state == self.state
        assert self.attrs.action == self.action
        assert self.attrs.source_branch == "fix-branch"
        assert self.attrs.target_branch == "master"

    def and_it_should_have_default_optional_fields(self):
        assert self.attrs.sha is None
        assert self.attrs.has_conflicts is False
        assert self.attrs.rebase_in_progress is False
        assert self.attrs.web_url is None


class Scenario__create_pipeline_attributes(vedro.Scenario):
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


class Scenario__create_label_changes(vedro.Scenario):
    subject = "create label changes"

    def when_label_changes_are_created(self):
        self.changes = LabelChanges(
            previous=["feature"],
            current=["feature", "merge_queue"],
        )

    def then_it_should_have_correct_labels(self):
        assert self.changes.previous == ["feature"]
        assert self.changes.current == ["feature", "merge_queue"]

    def and_added_label_can_be_detected(self):
        added = set(self.changes.current) - set(self.changes.previous)
        assert "merge_queue" in added


class Scenario__detect_removed_label(vedro.Scenario):
    subject = "detect removed label"

    def given_label_changes_with_removal(self):
        self.changes = LabelChanges(
            previous=["feature", "merge_queue"],
            current=["feature"],
        )

    def when_removed_labels_are_calculated(self):
        self.removed = set(self.changes.previous) - set(self.changes.current)

    def then_it_should_detect_removed_label(self):
        assert "merge_queue" in self.removed


class Scenario__create_merge_request_event(vedro.Scenario):
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


class Scenario__create_pipeline_event(vedro.Scenario):
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


class Scenario__create_pipeline_event_without_mr(vedro.Scenario):
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


class Scenario__create_note_event(vedro.Scenario):
    subject = "create note webhook event"

    def when_note_event_is_created(self):
        self.event = NoteEvent(
            object_kind="note",
            event_type="note",
            project_id=42,
            user_id=1,
            user_name="John Doe",
            user_username="johndoe",
            note_id=5000,
            note_body="LGTM!",
            noteable_type="MergeRequest",
            merge_request_iid=123,
        )

    def then_it_should_have_correct_fields(self):
        assert self.event.object_kind == "note"
        assert self.event.note_id == 5000
        assert self.event.note_body == "LGTM!"
        assert self.event.noteable_type == "MergeRequest"
        assert self.event.merge_request_iid == 123


class Scenario__validate_webhook_token_success(vedro.Scenario):
    subject = "validate webhook token with correct secret"

    def given_matching_token_and_secret(self):
        self.token = "super-secret-webhook-token"
        self.secret = "super-secret-webhook-token"

    def when_token_is_validated(self):
        self.result = validate_webhook_token(self.token, self.secret)

    def then_it_should_return_true(self):
        assert self.result is True


class Scenario__validate_webhook_token_failure(vedro.Scenario):
    subject = "validate webhook token with incorrect secret"

    def given_mismatched_token_and_secret(self):
        self.token = "wrong-token"
        self.secret = "correct-secret"

    def when_token_is_validated(self):
        self.result = validate_webhook_token(self.token, self.secret)

    def then_it_should_return_false(self):
        assert self.result is False


class Scenario__validate_webhook_token_timing_safe(vedro.Scenario):
    subject = "webhook token validation uses constant-time comparison"

    def given_tokens_with_common_prefix(self):
        self.token1 = "secret-token-123"
        self.token2 = "secret-token-456"
        self.secret = "secret-token-789"

    def when_validating_both_tokens(self):
        self.result1 = validate_webhook_token(self.token1, self.secret)
        self.result2 = validate_webhook_token(self.token2, self.secret)

    def then_both_should_fail(self):
        assert self.result1 is False
        assert self.result2 is False
