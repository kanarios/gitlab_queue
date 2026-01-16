"""Test validation fails for negative project ID."""

import vedro

from gitlab_queue.config import ConfigurationError, _validate_settings

from ._helpers import create_valid_settings


class Scenario(vedro.Scenario):
    subject = "try to validate settings with negative project id"

    def given_settings_with_negative_project_id(self):
        self.settings = create_valid_settings(gitlab_project_id=-1)

    def when_validating_settings(self):
        try:
            _validate_settings(self.settings)
            self.error = None
        except ConfigurationError as e:
            self.error = e

    def then_it_should_raise_configuration_error(self):
        assert self.error is not None
        assert "gitlab_project_id" in str(self.error)
        assert "positive" in str(self.error)
