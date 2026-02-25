"""Test that _mask_database_url masks the password in database URL."""

from __future__ import annotations

import vedro

from gitlab_queue.config import Settings, _mask_database_url


class Scenario(vedro.Scenario):
    subject = "database URL masking hides password"

    def given_settings_with_database_url(self):
        """
        Create and assign a Settings object whose database_url includes an embedded password.
        
        The Settings instance is stored on self.settings and uses database_url "postgresql://user:secret123@host/db" so the test can verify that the password ("secret123") is masked.
        """
        self.settings = Settings(
            gitlab_url="https://gitlab.com",
            gitlab_token="test-token",
            gitlab_project_id=1,
            jwt_secret="a" * 64,
            webhook_secret="test",
            database_url="postgresql://user:secret123@host/db",
        )

    def when_mask_database_url_is_called(self):
        """
        Mask the database URL from the scenario's Settings.
        
        Stores the masked database URL derived from self.settings into self.result.
        """
        self.result = _mask_database_url(self.settings)

    def then_password_is_not_in_result(self):
        """
        Verify that the plaintext password 'secret123' is not present in the masked database URL.
        
        Raises:
            AssertionError: if 'secret123' is found in self.result.
        """
        assert "secret123" not in self.result

    def and_mask_placeholder_is_in_result(self):
        """
        Asserts that the masked placeholder '***' appears in the masked database URL result.
        
        Raises:
            AssertionError: If '***' is not found in self.result.
        """
        assert "***" in self.result
