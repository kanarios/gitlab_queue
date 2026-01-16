from datetime import datetime

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database, create_mock_row
from scenarios.library import QueueState

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "convert database row to queue item"

    def given_queue_manager_and_row(self):
        self.db, _, _ = create_mock_database()
        self.queue_manager = QueueManager(db=self.db)
        self.row = create_mock_row(iid=789, status=QueueState.TESTING, is_hotfix=1)

    def when_row_is_converted(self):
        self.item = self.queue_manager._row_to_queue_item(self.row)

    def then_it_should_create_queue_item(self):
        assert isinstance(self.item, QueueItem)
        assert self.item.mr_iid == 789
        assert self.item.state == QueueState.TESTING
        assert self.item.is_hotfix is True

    def and_it_should_parse_datetime(self):
        assert self.item.queued_at is not None
        assert isinstance(self.item.queued_at, datetime)
