"""Test: _sanitize_response_body uses exact key matching, not substring."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import _sanitize_response_body


class Scenario__safe_keys_not_redacted(vedro.Scenario):
    subject = "sanitize does NOT redact safe keys like author, author_name, author_username"

    def given_body_with_safe_keys(self):
        self.body = {
            "author": {"name": "John"},
            "author_name": "John Doe",
            "author_username": "johndoe",
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_author_should_not_be_redacted(self):
        assert self.result["author"] == {"name": "John"}, f"Got {self.result['author']}"

    def and_author_name_should_not_be_redacted(self):
        assert self.result["author_name"] == "John Doe", f"Got {self.result['author_name']}"

    def and_author_username_should_not_be_redacted(self):
        assert self.result["author_username"] == "johndoe", f"Got {self.result['author_username']}"


class Scenario__sensitive_keys_redacted(vedro.Scenario):
    subject = "sanitize redacts truly sensitive keys"

    def given_body_with_sensitive_keys(self):
        self.body = {
            "access_token": "glpat-xxx",
            "password": "secret123",
            "private_token": "tok-yyy",
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_access_token_should_be_redacted(self):
        assert self.result["access_token"] == "***"

    def and_password_should_be_redacted(self):
        assert self.result["password"] == "***"

    def and_private_token_should_be_redacted(self):
        assert self.result["private_token"] == "***"


class Scenario__false_positive_keys_not_redacted(vedro.Scenario):
    subject = "sanitize does NOT redact keys that merely contain a sensitive substring"

    def given_body_with_false_positive_keys(self):
        self.body = {
            "ssh_key": "ssh-rsa AAAA...",
            "token_type": "bearer",
        }

    def when_body_is_sanitized(self):
        self.result = _sanitize_response_body(self.body)

    def then_ssh_key_should_not_be_redacted(self):
        assert self.result["ssh_key"] == "ssh-rsa AAAA...", f"Got {self.result['ssh_key']}"

    def and_token_type_should_not_be_redacted(self):
        assert self.result["token_type"] == "bearer", f"Got {self.result['token_type']}"
