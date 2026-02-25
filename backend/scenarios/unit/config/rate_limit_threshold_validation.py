"""Test that _validate_settings fails when critical <= warning threshold."""

from __future__ import annotations

import vedro

from gitlab_queue.config import ConfigurationError, Settings, _validate_settings


class Scenario(vedro.Scenario):
    subject = "rate limit threshold validation fails when critical <= warning"

    def given_settings_with_invalid_thresholds(self):
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
        try:
            _validate_settings(self.settings)
            self.raised = None
        except ConfigurationError as exc:
            self.raised = exc

    def then_configuration_error_is_raised(self):
        assert self.raised is not None

    def and_message_mentions_threshold(self):
        assert "rate_limit_critical_threshold" in str(self.raised)
