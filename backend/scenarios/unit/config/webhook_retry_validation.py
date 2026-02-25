"""Test that _validate_settings fails when max delay < base delay."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "webhook retry validation fails when max delay < base delay"

    def given_settings_with_invalid_retry_delays(self):
        """
        Initialize self.settings with a Settings instance configured so webhook_retry_max_delay_seconds (10) is less than webhook_retry_base_delay_seconds (100), to trigger validation failure.
        
        The Settings includes minimal required GitLab connection fields and secrets for the test.
        """
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            webhook_retry_max_delay_seconds=10,
            webhook_retry_base_delay_seconds=100,
        )

    def when_validate_settings_is_called(self):
        """
        Validate the scenario's settings and record any ConfigurationError on self.raised.
        
        Sets self.raised to the caught ConfigurationError if validation fails; otherwise sets it to None.
        """
        try:
            _validate_settings(self.settings)
            self.raised = None
        except ConfigurationError as exc:
            self.raised = exc

    def then_configuration_error_is_raised(self):
        """
        Asserts that a ConfigurationError was raised during settings validation.
        
        Raises an AssertionError if no exception was captured (i.e., if self.raised is None).
        """
        assert self.raised is not None

    def and_message_mentions_webhook_retry(self):
        """
        Asserts that the caught ConfigurationError message mentions the webhook retry max-delay setting.
        
        Raises an AssertionError if "webhook_retry_max_delay_seconds" is not present in the string representation of the stored exception.
        """
        assert "webhook_retry_max_delay_seconds" in str(self.raised), (
            f"Expected webhook retry mentioned in error, got: {self.raised}"
        )
