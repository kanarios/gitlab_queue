"""Test notify() raises KeyError for an unknown status string."""

from __future__ import annotations

import vedro
from vedro import catched

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "notify() raises KeyError for unknown status"

    def given_notifier_with_unknown_status(self):
        """
        Prepare a test notifier and an invalid status identifier for the scenario.

        Sets `self.notifier` to a test notifier instance and `self.unknown_status` to a string that does not correspond to any valid status, to be used when asserting that `notify()` raises a KeyError for unknown statuses.
        """
        self.notifier = create_test_notifier()
        self.unknown_status = "this_status_does_not_exist"

    async def when_notify_is_called_with_unknown_status(self):
        """
        Calls the notifier with an unknown status to trigger a KeyError.

        The raised KeyError is caught and stored in self.exc_info by the catched context manager.
        """
        with catched(KeyError) as self.exc_info:
            await self.notifier.notify(mr_iid=42, status=self.unknown_status)

    def then_key_error_is_raised(self):
        """
        Asserts that the captured exception is a KeyError.

        Raises an AssertionError if the stored exception type (self.exc_info.type) is not KeyError.
        """
        assert self.exc_info.type is KeyError

    def and_error_message_mentions_the_status(self):
        """
        Asserts that the caught KeyError's message contains the unknown status string.
        """
        assert self.unknown_status in str(self.exc_info.value)
