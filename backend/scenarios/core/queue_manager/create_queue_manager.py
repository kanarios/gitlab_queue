"""Scenario: create queue manager."""

import vedro
from scenarios.core.queue_manager._helpers import create_mock_database

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "create queue manager"

    def given_mock_database(self):
        self.db, _, _ = create_mock_database()

    def when_queue_manager_is_created(self):
        self.queue_manager = QueueManager(db=self.db)

    def then_it_should_have_database_reference(self):
        assert self.queue_manager.db is self.db
