"""Test merged, failed, and removed are final states."""

import vedro

from gitlab_queue.core.state_machine import MRStateMachine


class Scenario(vedro.Scenario):
    subject = "merged, failed, and removed are final states"

    def given_state_machine_class(self):
        pass

    def when_checking_final_states(self):
        self.merged_is_final = MRStateMachine.merged.final
        self.failed_is_final = MRStateMachine.failed.final
        self.removed_is_final = MRStateMachine.removed.final

    def then_all_should_be_final(self):
        assert self.merged_is_final is True
        assert self.failed_is_final is True
        assert self.removed_is_final is True
