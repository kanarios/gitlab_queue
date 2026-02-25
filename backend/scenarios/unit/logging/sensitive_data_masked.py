"""Test that sensitive data (tokens, passwords) is masked in log output."""

from __future__ import annotations

import vedro

from gitlab_queue.utils.logging import _mask_sensitive_value


class Scenario(vedro.Scenario):
    subject = "GitLab personal access token is masked"

    def given_string_with_gitlab_token(self):
        self.input_value = "Authorization: glpat-abc123def456_xyz"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_token_should_be_masked(self):
        assert "glpat-abc123def456_xyz" not in self.result
        assert "glpat-***" in self.result


class Scenario2(vedro.Scenario):
    subject = "database URL credentials are masked"

    def given_string_with_db_credentials(self):
        """
        Set up a test input containing a PostgreSQL URL with embedded credentials.
        
        This assigns a connection string with username `admin` and password `supersecret` to `self.input_value` for use in sensitive-data masking tests.
        """
        self.input_value = "postgresql://admin:supersecret@localhost/mydb"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_password_should_be_masked(self):
        """
        Asserts that a database connection string's password is replaced with a mask while the username and host/path remain.
        
        This test verifies that the original password "supersecret" does not appear in the masked result and that the credentials portion is shown as "admin:***@".
        """
        assert "supersecret" not in self.result
        assert "admin:***@" in self.result

    def and_host_and_path_should_be_preserved(self):
        """
        Assert that the host and path of the database URL remain unchanged after masking.
        
        Checks that "localhost/mydb" is present in self.result.
        """
        assert "localhost/mydb" in self.result


class Scenario3(vedro.Scenario):
    subject = "Bearer token is masked"

    def given_string_with_bearer_token(self):
        """
        Set up a test input string containing an HTTP Bearer token (JWT) assigned to self.input_value.
        
        The string includes a sample JWT-like value ("eyJhbGciOiJIUzI1NiJ9.payload.signature") and is marked to be ignored by secret scanners.
        """
        self.input_value = "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_bearer_token_should_be_masked(self):
        assert "eyJhbGciOiJIUzI1NiJ9" not in self.result
        assert "Bearer ***" in self.result


class Scenario4(vedro.Scenario):
    subject = "password in key=value format is masked"

    def given_string_with_password_key_value(self):
        """
        Set the scenario input to a key=value pair where the value is a plaintext password.
        
        The function assigns "password=my_secret_password123" to self.input_value for use in masking verification.
        """
        self.input_value = "password=my_secret_password123"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_password_value_should_be_masked(self):
        assert "my_secret_password123" not in self.result
        assert "password=***" in self.result


class Scenario5(vedro.Scenario):
    subject = "Private-Token header is masked"

    def given_string_with_private_token_header(self):
        self.input_value = "Private-Token: glpat-some_secret_token_here"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_token_value_should_be_masked(self):
        """
        Assert that a 'Private-Token' header value has been masked in the stored result.
        
        Checks that the original token substring is not present and that the header appears as
        "Private-Token: ***" in self.result.
        """
        assert "some_secret_token_here" not in self.result
        assert "Private-Token: ***" in self.result


class Scenario6(vedro.Scenario):
    subject = "safe string is not modified"

    def given_string_without_sensitive_data(self):
        self.input_value = "Processing MR !42 on branch feature/login"

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_string_should_be_unchanged(self):
        """
        Asserts that the masked result is identical to the original input string.
        
        Raises:
            AssertionError: If the result differs from the original input.
        """
        assert self.result == self.input_value


class Scenario7(vedro.Scenario):
    subject = "GitLab deploy token is masked"

    def given_string_with_deploy_token(self):
        """
        Sets self.input_value to a string containing a GitLab deploy token used to verify masking behavior.
        """
        self.input_value = "Token: gldt-abcdefg123456"  # gitleaks:allow

    def when_mask_is_applied(self):
        """
        Apply sensitive-data masking to the prepared input and store the masked result on the instance.
        
        Sets self.result to the masked form of self.input_value.
        """
        self.result = _mask_sensitive_value(self.input_value)

    def then_deploy_token_should_be_masked(self):
        assert "gldt-abcdefg123456" not in self.result
        assert "gldt-***" in self.result
