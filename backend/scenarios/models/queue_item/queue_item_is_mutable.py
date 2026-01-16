"""Unit tests for QueueItem model."""

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
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
