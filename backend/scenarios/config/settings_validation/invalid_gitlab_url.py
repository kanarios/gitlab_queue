"""Test validation fails for invalid gitlab URL."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with invalid gitlab url"

    def given_settings_with_invalid_url(self):
        self.settings = create_valid_settings(gitlab_url="ftp://gitlab.com")

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "gitlab_url" in str(self.error)
        assert "http" in str(self.error)
