"""BUG-16: Dead SQL constant _COUNT_POSITION_SQL should not exist in queue module."""

import vedro

from gitlab_queue.core import queue as queue_module


class Scenario(vedro.Scenario):
    subject = "queue module does not contain dead _COUNT_POSITION_SQL constant"

    def given_queue_module(self):
        self.module = queue_module

    def when_checking_for_dead_constant(self):
        self.has_constant = hasattr(self.module, "_COUNT_POSITION_SQL")

    def then_constant_should_not_exist(self):
        assert not self.has_constant, "_COUNT_POSITION_SQL is dead code and should be removed from queue module"
