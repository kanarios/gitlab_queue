"""Test validation fails for zero poll interval."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with zero poll interval"

    def given_settings_with_zero_poll_interval(self):
        self.settings = create_valid_settings(poll_interval_seconds=0)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "poll_interval_seconds" in str(self.error)
