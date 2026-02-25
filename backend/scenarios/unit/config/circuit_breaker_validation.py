"""Test that _validate_settings fails on invalid circuit breaker thresholds."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "circuit breaker validation fails on invalid threshold"

    def given_settings_with_zero_failure_threshold(self):
        """
        Prepare self.settings with a Settings instance whose circuit_breaker_failure_threshold is set to 0 (invalid) and populated with valid GitLab/auth fields.
        
        This setup is used to trigger validation logic that should reject a zero failure threshold.
        """
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            circuit_breaker_failure_threshold=0,
        )

    def when_validate_settings_is_called(self):
        """
        Call _validate_settings with the scenario's settings and capture any ConfigurationError.
        
        If _validate_settings raises a ConfigurationError, assign it to self.raised; otherwise set self.raised to None.
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
            AssertionError: If no ConfigurationError was captured in self.raised.
        """
        assert self.raised is not None

    def and_message_mentions_circuit_breaker(self):
        assert "circuit_breaker_failure_threshold" in str(self.raised)
