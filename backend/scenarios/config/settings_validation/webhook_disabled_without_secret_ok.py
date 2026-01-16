"""Test validation passes when webhook disabled without secret."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "validation passes when webhook disabled without secret"

    def given_settings_with_webhook_disabled(self):
        self.settings = create_valid_settings(
            webhook_enabled=False,
            webhook_secret=None,
        )

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_validation_should_pass(self):
        assert self.error is None
