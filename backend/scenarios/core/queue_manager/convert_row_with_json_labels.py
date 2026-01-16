"""Scenario: convert row with JSON labels to QueueItem."""

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row
from scenarios.library import Labels

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "convert row with json labels to queue item"

    def given_row_with_labels(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["labels"] = f'["{Labels.FEATURE}", "urgent", "{Labels.MERGE_QUEUE}"]'

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_parse_labels(self):
        assert self.item.labels == [Labels.FEATURE, "urgent", Labels.MERGE_QUEUE]
