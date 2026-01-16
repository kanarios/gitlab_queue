"""Test validation fails when max delay less than base delay."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with max delay less than base delay"

    def given_settings_with_invalid_delays(self):
        self.settings = create_valid_settings(
            webhook_retry_base_delay_seconds=300,
            webhook_retry_max_delay_seconds=100,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "webhook_retry_max_delay_seconds" in str(self.error)
