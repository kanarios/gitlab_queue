"""Test PollingConfig stores values correctly."""

import vedro
from vedro import params

from gitlab_queue.core.polling import PollingConfig


class Scenario(vedro.Scenario):
    subject = "PollingConfig stores {field}={value}"

    @params("timeout_seconds", 120.0)
    @params("poll_interval_seconds", 10.0)
    def __init__(self, field: str, value: float):
        self.field = field
        self.value = value

    def given_polling_config_with_values(self):
        kwargs = {self.field: self.value}
        defaults = {"timeout_seconds": 1.0, "poll_interval_seconds": 1.0}
        defaults.update(kwargs)
        self.config = PollingConfig(**defaults)

    def when_field_is_accessed(self):
        self.actual_value = getattr(self.config, self.field)

    def then_field_has_expected_value(self):
        assert self.actual_value == self.value
