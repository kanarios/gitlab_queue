"""Test queued is the initial state."""

import vedro

from gitlab_queue.core.state_machine import MRStateMachine


class Scenario(vedro.Scenario):
    subject = "queued is the initial state"

    def when_checking_initial_state(self):
        self.is_initial = MRStateMachine.queued.initial

    def then_queued_should_be_initial(self):
        assert self.is_initial is True
