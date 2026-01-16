"""Scenario: convert row with timestamps to QueueItem."""

from datetime import UTC, datetime

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "convert row with timestamps to queue item"

    def given_row_with_timestamps(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.now = datetime.now(UTC)
        self.row = create_mock_row()
        self.row["started_at"] = self.now.isoformat()
        self.row["finished_at"] = self.now.isoformat()

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_parse_timestamps(self):
        assert self.item.started_at is not None
        assert self.item.finished_at is not None
        assert isinstance(self.item.started_at, datetime)
        assert isinstance(self.item.finished_at, datetime)
