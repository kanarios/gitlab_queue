"""Test that _row_to_queue_item extracts project_id from database row."""

from __future__ import annotations

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "row to queue item preserves project_id"

    def given_queue_manager(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)

    def given_row_with_project_id(self):
        self.row = create_mock_row(iid=42, project_id=77777)

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_project_id_matches(self):
        assert self.item.project_id == 77777

    def and_iid_matches(self):
        assert self.item.mr_iid == 42
