"""Unit tests for QueueItem model."""

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
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
