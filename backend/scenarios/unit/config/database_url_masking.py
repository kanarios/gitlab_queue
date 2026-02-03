"""Test that _mask_database_url masks the password in database URL."""

from __future__ import annotations

import vedro

from gitlab_queue.config import Settings, _mask_database_url


class Scenario(vedro.Scenario):
    subject = "database URL masking hides password"

    def given_settings_with_database_url(self):
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            database_url="postgresql://user:secret123@host/db",
        )

    def when_mask_database_url_is_called(self):
        self.result = _mask_database_url(self.settings)

    def then_password_is_not_in_result(self):
        assert "secret123" not in self.result, f"Expected password to be masked, got: {self.result}"

    def and_mask_placeholder_is_in_result(self):
        assert "***" in self.result, f"Expected '***' in masked URL, got: {self.result}"
