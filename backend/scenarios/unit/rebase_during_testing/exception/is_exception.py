"""Test RebaseRetryLimitExceeded is Exception subclass."""

import vedro

from gitlab_queue.core.rebase_during_testing import RebaseRetryLimitExceeded


class Scenario(vedro.Scenario):
    subject = "RebaseRetryLimitExceeded is Exception subclass"

    def given_rebase_retry_limit_exceeded(self):
        self.exc = RebaseRetryLimitExceeded("test message")

    def then_is_exception_subclass(self):
        assert isinstance(self.exc, Exception)
