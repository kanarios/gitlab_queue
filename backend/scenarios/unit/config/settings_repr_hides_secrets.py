"""Test that repr(settings) masks tokens and secrets."""

from __future__ import annotations

import vedro

from gitlab_queue.config import Settings


class Scenario(vedro.Scenario):
    subject = "settings repr hides secrets"

    def given_settings_with_secrets(self):
        """
        Prepare a Settings instance populated with secret values for testing representation masking.

        Creates sample secret strings for a GitLab token, a JWT secret, and a webhook secret, then constructs a Settings object using those values along with a GitLab URL and project ID and stores it on the scenario instance for later assertions.
        """
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
        """
        Capture and store the string representation of the Settings instance.

        Sets self.result to the value of repr(self.settings).
        """
        self.result = repr(self.settings)

    def then_mask_placeholder_is_in_result(self):
        assert "***" in self.result

    def and_token_value_is_not_in_result(self):
        """
        Asserts that the original GitLab token value does not appear in the stored repr result.

        This verifies that the sensitive gitlab token is masked in the Settings string representation.
        """
        assert self.token_value not in self.result

    def and_jwt_value_is_not_in_result(self):
        """
        Asserts that the JWT secret value does not appear in the stored representation result.

        This verifies that sensitive JWT content is masked or omitted from repr(self.settings).
        """
        assert self.jwt_value not in self.result

    def and_webhook_value_is_not_in_result(self):
        assert self.webhook_value not in self.result

    def and_webhook_secret_is_masked(self):
        assert "webhook_secret=Secret('***')" in self.result
