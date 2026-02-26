"""Test that _validate_settings fails when critical <= warning threshold."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "rate limit threshold validation fails when critical <= warning"

    def given_settings_with_invalid_thresholds(self):
        """
        Create and assign to self.settings a Settings instance whose rate limit thresholds are invalid (rate_limit_critical_threshold is less than or equal to rate_limit_warning_threshold).

        The Settings also contains placeholder values for gitlab_url, gitlab_token, gitlab_project_id, jwt_secret, and webhook_secret used by the scenario.
        """
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            rate_limit_critical_threshold=0.7,
            rate_limit_warning_threshold=0.8,
        )

    def when_validate_settings_is_called(self):
        """
        Validate the scenario's settings and record any ConfigurationError raised.

        If validation succeeds, sets self.raised to None. If a ConfigurationError is raised, stores it in self.raised.
        """
        try:
            _validate_settings(self.settings)
            self.raised = None
        except ConfigurationError as exc:
            self.raised = exc

    def then_configuration_error_is_raised(self):
        """
        Asserts that a ConfigurationError was raised during validation.

        Raises:
            AssertionError: If no exception was captured in self.raised.
        """
        assert self.raised is not None

    def and_message_mentions_threshold(self):
        """
        Asserts that the captured ConfigurationError message mentions the critical threshold key.

        Raises an AssertionError if the string "rate_limit_critical_threshold" is not present in the string representation of the captured exception.
        """
        assert "rate_limit_critical_threshold" in str(self.raised)
