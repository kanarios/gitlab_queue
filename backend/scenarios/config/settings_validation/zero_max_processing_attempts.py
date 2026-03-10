"""Test validation fails for zero max_processing_attempts."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with zero max processing attempts"

    def given_settings_with_zero_attempts(self):
        self.settings = create_valid_settings(max_processing_attempts=0)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "max_processing_attempts" in str(self.error)
