"""Test PollingConfig is frozen (immutable)."""

from dataclasses import FrozenInstanceError

import vedro
from vedro import catched

from gitlab_queue.core.polling import PollingConfig


class Scenario(vedro.Scenario):
    subject = "PollingConfig is frozen (immutable)"

    def given_polling_config(self):
        self.config = PollingConfig(
            timeout_seconds=60.0,
            poll_interval_seconds=5.0,
        )

    def when_attempting_to_modify_field(self):
        with catched(FrozenInstanceError) as self.exception:
            self.config.timeout_seconds = 120.0

    def then_frozen_instance_error_is_raised(self):
        assert self.exception.type is FrozenInstanceError
