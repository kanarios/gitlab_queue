"""Test that sensitive data (tokens, passwords) is masked in log output."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.logging import _mask_sensitive_value


class Scenario(vedro.Scenario):
    subject = "GitLab personal access token is masked"

    def given_string_with_gitlab_token(self):
        self.input_value = "Authorization: glpat-abc123def456_xyz"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_token_should_be_masked(self):
        assert "glpat-abc123def456_xyz" not in self.result
        assert "glpat-***" in self.result


class Scenario2(vedro.Scenario):
    subject = "database URL credentials are masked"

    def given_string_with_db_credentials(self):
        self.input_value = "postgresql://admin:supersecret@localhost/mydb"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_password_should_be_masked(self):
        assert "supersecret" not in self.result
        assert "***" in self.result

    def and_username_should_be_preserved(self):
        assert "admin" in self.result


class Scenario3(vedro.Scenario):
    subject = "Bearer token is masked"

    def given_string_with_bearer_token(self):
        self.input_value = "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_bearer_token_should_be_masked(self):
        assert "eyJhbGciOiJIUzI1NiJ9" not in self.result
        assert "Bearer ***" in self.result or "***JWT***" in self.result


class Scenario4(vedro.Scenario):
    subject = "password in key=value format is masked"

    def given_string_with_password_key_value(self):
        self.input_value = "password=my_secret_password123"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_password_value_should_be_masked(self):
        assert "my_secret_password123" not in self.result
        assert "password=***" in self.result


class Scenario5(vedro.Scenario):
    subject = "Private-Token header is masked"

    def given_string_with_private_token_header(self):
        self.input_value = "Private-Token: glpat-some_secret_token_here"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_token_value_should_be_masked(self):
        assert "some_secret_token_here" not in self.result


class Scenario6(vedro.Scenario):
    subject = "safe string is not modified"

    def given_string_without_sensitive_data(self):
        self.input_value = "Processing MR !42 on branch feature/login"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_string_should_be_unchanged(self):
        assert self.result == self.input_value


class Scenario7(vedro.Scenario):
    subject = "GitLab deploy token is masked"

    def given_string_with_deploy_token(self):
        self.input_value = "Token: gldt-abcdefg123456"

    def when_mask_is_applied(self):
        self.result = _mask_sensitive_value(self.input_value)

    def then_deploy_token_should_be_masked(self):
        assert "gldt-abcdefg123456" not in self.result
        assert "gldt-***" in self.result
