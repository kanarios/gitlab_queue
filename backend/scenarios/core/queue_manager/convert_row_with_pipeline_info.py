"""Scenario: convert row with pipeline info to QueueItem."""

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "convert row with pipeline info to queue item"

    def given_row_with_pipeline(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row()
        self.row["pipeline_id"] = 12345
        self.row["pipeline_status"] = "running"
        self.row["retry_count"] = 2
        self.row["last_error"] = "Previous pipeline failed"

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_include_pipeline_info(self):
        assert self.item.pipeline_id == 12345
        assert self.item.pipeline_status == "running"
        assert self.item.retry_count == 2
        assert self.item.last_error == "Previous pipeline failed"
