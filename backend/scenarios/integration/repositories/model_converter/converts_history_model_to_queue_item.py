"""Test that ModelConverter converts MergeRequestHistoryModel to QueueItem."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.integration.repositories._helpers import create_test_history_model

from gitlab_queue.db.repositories import ModelConverter
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "model converter converts history model to queue item"

    def given_history_model(self):
        now = datetime.now(UTC)
        self.history = create_test_history_model(
            iid=42,
            title="Completed MR",
            author_name="Test User",
            author_username="testuser",
            author_avatar="https://avatar.url/test.png",
            status="merged",
            is_hotfix=1,
            labels='["merge_queue"]',
            target_branch="main",
            queued_at=(now - timedelta(minutes=10)).isoformat(),
            started_at=(now - timedelta(minutes=5)).isoformat(),
            finished_at=now.isoformat(),
            failure_reason=None,
            pipeline_id=5678,
            pipeline_status="success",
        )

    def when_history_model_is_converted(self):
        self.item = ModelConverter.history_model_to_queue_item(self.history)

    def then_queue_item_fields_should_match(self):
        assert isinstance(self.item, QueueItem)
        assert self.item.mr_iid == 42
        assert self.item.title == "Completed MR"
        assert self.item.author_name == "Test User"
        assert self.item.author_username == "testuser"
        assert self.item.author_avatar == "https://avatar.url/test.png"
        assert self.item.state == "merged"
        assert self.item.is_hotfix is True
        assert self.item.labels == ["merge_queue"]
        assert self.item.target_branch == "main"
        assert self.item.pipeline_id == 5678
        assert self.item.pipeline_status == "success"
        assert self.item.retry_count == 0
        assert self.item.stale_warning_sent is False

    def and_timestamps_should_be_parsed(self):
        assert self.item.queued_at is not None
        assert self.item.started_at is not None
        assert self.item.finished_at is not None

    async def do_cleanup(self):
        pass
