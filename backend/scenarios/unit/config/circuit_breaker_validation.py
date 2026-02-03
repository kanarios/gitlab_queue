"""Test that _validate_settings fails on invalid circuit breaker thresholds."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "circuit breaker validation fails on invalid threshold"

    def given_settings_with_zero_failure_threshold(self):
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            circuit_breaker_failure_threshold=0,
        )

    def when_validate_settings_is_called(self):
        try:
            _validate_settings(self.settings)
            self.raised = None
        except ConfigurationError as exc:
            self.raised = exc

    def then_configuration_error_is_raised(self):
        assert self.raised is not None, "Expected ConfigurationError to be raised"

    def and_message_mentions_circuit_breaker(self):
        assert "circuit_breaker_failure_threshold" in str(self.raised), (
            f"Expected circuit breaker mentioned in error, got: {self.raised}"
        )
