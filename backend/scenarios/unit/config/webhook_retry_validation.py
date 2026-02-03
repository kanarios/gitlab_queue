"""Test that _validate_settings fails when max delay < base delay."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "webhook retry validation fails when max delay < base delay"

    def given_settings_with_invalid_retry_delays(self):
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
        try:
            _validate_settings(self.settings)
            self.raised = None
        except ConfigurationError as exc:
            self.raised = exc

    def then_configuration_error_is_raised(self):
        assert self.raised is not None, "Expected ConfigurationError to be raised"

    def and_message_mentions_webhook_retry(self):
        assert "webhook_retry_max_delay_seconds" in str(self.raised), (
            f"Expected webhook retry mentioned in error, got: {self.raised}"
        )
