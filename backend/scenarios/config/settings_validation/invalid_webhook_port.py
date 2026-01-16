"""Test validation fails for invalid webhook port."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with invalid webhook port"

    def given_settings_with_invalid_port(self):
        self.settings = create_valid_settings(webhook_port=70000)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "webhook_port" in str(self.error)
        assert "65535" in str(self.error)
