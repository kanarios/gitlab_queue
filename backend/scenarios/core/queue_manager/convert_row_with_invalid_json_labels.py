"""Scenario: convert row with invalid JSON labels gracefully."""

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "convert row with invalid json labels gracefully"

    def given_row_with_invalid_json_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row(iid=999)
        self.row["labels"] = "not valid json {"

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_labels_should_be_empty_list(self):
        assert self.item.labels == []

    def and_item_should_be_valid(self):
        assert self.item.mr_iid == 999
