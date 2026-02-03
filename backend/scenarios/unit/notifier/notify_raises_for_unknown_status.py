"""Test notify() raises KeyError for an unknown status string."""

from __future__ import annotations

import vedro
from vedro import catched

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "notify() raises KeyError for unknown status"

    def given_notifier_with_unknown_status(self):
        self.notifier = create_test_notifier()
        self.unknown_status = "this_status_does_not_exist"

    async def when_notify_is_called_with_unknown_status(self):
        with catched(KeyError) as self.exc_info:
            await self.notifier.notify(mr_iid=42, status=self.unknown_status)

    def then_key_error_is_raised(self):
        assert self.exc_info.type is KeyError

    def and_error_message_mentions_the_status(self):
        assert self.unknown_status in str(self.exc_info.value)
