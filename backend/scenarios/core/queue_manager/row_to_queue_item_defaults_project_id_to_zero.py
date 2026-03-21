"""Test that _row_to_queue_item defaults project_id to 0 when missing from row."""

from __future__ import annotations

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "row to queue item defaults project_id to 0 when missing"

    def given_queue_manager(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)

    def given_row_without_project_id(self):
        self.row = create_mock_row(iid=42)
        del self.row["project_id"]

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_project_id_defaults_to_zero(self):
        assert self.item.project_id == 0
