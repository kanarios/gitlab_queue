"""Scenario: QueueItemNotFoundError contains MR IID."""

import vedro

from gitlab_queue.core.queue import QueueItemNotFoundError


class Scenario(vedro.Scenario):
    subject = "queue item not found error contains mr iid"

    def given_mr_iid(self):
        self.mr_iid = 456

    def when_error_is_created(self):
        self.error = QueueItemNotFoundError(self.mr_iid)

    def then_it_should_contain_mr_iid(self):
        assert self.error.mr_iid == self.mr_iid
        assert "456" in str(self.error)
        assert "not found" in str(self.error).lower()
