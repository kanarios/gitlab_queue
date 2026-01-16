"""Scenario: QueueError is base exception for queue operations."""

import vedro

from gitlab_queue.core.queue import QueueError, QueueItemNotFoundError


class Scenario(vedro.Scenario):
    subject = "queue error is base exception for queue operations"

    def when_checking_inheritance(self):
        self.is_base_class = issubclass(QueueItemNotFoundError, QueueError)

    def then_it_should_be_subclass(self):
        assert self.is_base_class is True
