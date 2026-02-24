"""Test that repr(settings) masks tokens and secrets."""

from __future__ import annotations

import vedro

from gitlab_queue.config import Settings


class Scenario(vedro.Scenario):
    subject = "settings repr hides secrets"

    def given_settings_with_secrets(self):
        self.token_value = "glpat-super-secret-token"
        self.jwt_value = "b" * 64
        self.webhook_value = "webhook-secret-value"
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token=self.token_value,
            gitlab_project_id=1,
            jwt_secret=self.jwt_value,
            webhook_secret=self.webhook_value,
        )

    def when_repr_is_called(self):
        self.result = repr(self.settings)

    def then_mask_placeholder_is_in_result(self):
        assert "***" in self.result, f"Expected '***' in repr, got: {self.result}"

    def and_token_value_is_not_in_result(self):
        assert self.token_value not in self.result, f"Expected token '{self.token_value}' to be hidden in repr"

    def and_jwt_value_is_not_in_result(self):
        assert self.jwt_value not in self.result, "Expected jwt_secret to be hidden in repr"

    def and_webhook_value_is_not_in_result(self):
        assert self.webhook_value not in self.result, "Expected webhook_secret to be hidden in repr"

    def and_webhook_secret_is_masked(self):
        assert "webhook_secret='***'" in self.result or "webhook_secret=***" in self.result
