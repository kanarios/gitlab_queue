"""Test validation fails for wildcard CORS origin."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with wildcard cors origin"

    def given_settings_with_wildcard_cors(self):
        self.settings = create_valid_settings(cors_origins=["*"])

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "Wildcard" in str(self.error) or "CORS" in str(self.error)
