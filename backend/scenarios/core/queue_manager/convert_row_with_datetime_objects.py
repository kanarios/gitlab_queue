"""Scenario: convert row with datetime objects (not strings)."""

from datetime import UTC, datetime

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "convert row with datetime objects"

    def given_row_with_datetime_objects(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.now = datetime.now(UTC)
        self.row = create_mock_row()
        self.row["queued_at"] = self.now  # datetime object, not string
        self.row["started_at"] = self.now
        self.row["finished_at"] = self.now

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_handle_datetime_objects(self):
        assert self.item.queued_at == self.now
        assert self.item.started_at == self.now
        assert self.item.finished_at == self.now
