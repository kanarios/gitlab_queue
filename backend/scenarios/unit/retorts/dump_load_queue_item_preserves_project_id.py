"""Test that dump/load round-trip preserves project_id on QueueItem."""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.models.queue_item import QueueItem
from gitlab_queue.models.retorts import dump_queue_item, load_queue_item


class Scenario(vedro.Scenario):
    subject = "dump and load queue item preserves project_id"

    def given_queue_item_with_project_id(self):
        self.item = QueueItem(
            mr_iid=42,
            title="Test MR",
            author_name="User",
            author_username="user",
            target_branch="master",
            state="queued",
            queued_at=datetime(2026, 1, 1, tzinfo=UTC),
            project_id=12345,
        )

    def when_item_is_dumped_and_loaded(self):
        dumped = dump_queue_item(self.item)
        self.restored = load_queue_item(dumped)

    def then_project_id_is_preserved(self):
        assert self.restored.project_id == 12345

    def and_other_fields_are_preserved(self):
        assert self.restored.mr_iid == self.item.mr_iid
        assert self.restored.title == self.item.title
