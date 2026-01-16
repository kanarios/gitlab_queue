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
