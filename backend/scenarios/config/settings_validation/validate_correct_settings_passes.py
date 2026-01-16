"""Test that valid settings pass validation."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "validate correct settings passes"

    def given_valid_settings(self):
        self.settings = create_valid_settings()

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_validation_should_pass(self):
        assert self.error is None
