"""Test RebaseRetryLimitExceeded stores error message."""

import vedro

from gitlab_queue.core.rebase_during_testing import RebaseRetryLimitExceeded


class Scenario(vedro.Scenario):
    subject = "RebaseRetryLimitExceeded stores error message"

    def given_error_message(self):
        self.message = "MR !42: 3/3 rebase attempts exhausted"

    def when_exception_is_created(self):
        self.exc = RebaseRetryLimitExceeded(self.message)

    def then_message_is_stored(self):
        assert str(self.exc) == self.message

    def and_args_contains_message(self):
        assert self.exc.args[0] == self.message
