"""Test validation fails for negative pipeline timeout."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with negative pipeline timeout"

    def given_settings_with_negative_timeout(self):
        self.settings = create_valid_settings(pipeline_timeout_seconds=-100)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "pipeline_timeout_seconds" in str(self.error)
