"""Unit tests for QueueItem model."""

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "create queue item with required fields"

    def given_required_fields(self):
        self.mr_iid = 123
        self.title = "Fix bug in login"
        self.author_name = "John Doe"
        self.author_username = "johndoe"
        self.target_branch = "master"
        self.state = "queued"
        self.queued_at = datetime.now(UTC)

    def when_queue_item_is_created(self):
        self.queue_item = QueueItem(
            mr_iid=self.mr_iid,
            title=self.title,
            author_name=self.author_name,
            author_username=self.author_username,
            target_branch=self.target_branch,
            state=self.state,
            queued_at=self.queued_at,
        )

    def then_it_should_have_correct_required_fields(self):
        assert self.queue_item.mr_iid == self.mr_iid
        assert self.queue_item.title == self.title
        assert self.queue_item.author_name == self.author_name
        assert self.queue_item.author_username == self.author_username
        assert self.queue_item.target_branch == self.target_branch
        assert self.queue_item.state == self.state
        assert self.queue_item.queued_at == self.queued_at

    def and_it_should_have_default_optional_fields(self):
        assert self.queue_item.is_hotfix is False
        assert self.queue_item.author_avatar is None
        assert self.queue_item.labels == []
        assert self.queue_item.started_at is None
        assert self.queue_item.finished_at is None
        assert self.queue_item.pipeline_id is None
        assert self.queue_item.pipeline_status is None
        assert self.queue_item.retry_count == 0
        assert self.queue_item.last_error is None


class Scenario__create_queue_item_with_all_fields(vedro.Scenario):
    subject = "create queue item with all optional fields"

    def given_all_fields(self):
        self.now = datetime.now(UTC)
        self.started_at = datetime.now(UTC)
        self.finished_at = datetime.now(UTC)

    def when_queue_item_is_created_with_all_fields(self):
        self.queue_item = QueueItem(
            mr_iid=456,
            title="Add new feature",
            author_name="Jane Doe",
            author_username="janedoe",
            target_branch="main",
            state="merged",
            queued_at=self.now,
            is_hotfix=True,
            author_avatar="https://gitlab.com/avatar.png",
            labels=["feature", "urgent"],
            started_at=self.started_at,
            finished_at=self.finished_at,
            pipeline_id=789,
            pipeline_status="success",
            retry_count=2,
            last_error="Previous pipeline failed",
        )

    def then_it_should_have_all_fields_set(self):
        assert self.queue_item.is_hotfix is True
        assert self.queue_item.author_avatar == "https://gitlab.com/avatar.png"
        assert self.queue_item.labels == ["feature", "urgent"]
        assert self.queue_item.started_at == self.started_at
        assert self.queue_item.finished_at == self.finished_at
        assert self.queue_item.pipeline_id == 789
        assert self.queue_item.pipeline_status == "success"
        assert self.queue_item.retry_count == 2
        assert self.queue_item.last_error == "Previous pipeline failed"


class Scenario__queue_item_is_mutable(vedro.Scenario):
    subject = "queue item is mutable"

    def given_queue_item(self):
        self.queue_item = QueueItem(
            mr_iid=123,
            title="Test MR",
            author_name="Test User",
            author_username="testuser",
            target_branch="master",
            state="queued",
            queued_at=datetime.now(UTC),
        )

    def when_state_is_changed(self):
        self.queue_item.state = "rebasing"

    def then_state_should_be_updated(self):
        assert self.queue_item.state == "rebasing"
