"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import validate_webhook_token


class Scenario(vedro.Scenario):
    subject = "validate webhook token with incorrect secret"

    def given_mismatched_token_and_secret(self):
        self.token = "wrong-token"
        self.secret = "correct-secret"

    def when_token_is_validated(self):
        self.result = validate_webhook_token(self.token, self.secret)

    def then_it_should_return_false(self):
        assert self.result is False
