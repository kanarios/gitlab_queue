"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import validate_webhook_token


class Scenario(vedro.Scenario):
    subject = "validate webhook token with correct secret"

    def given_matching_token_and_secret(self):
        self.token = "super-secret-webhook-token"
        self.secret = "super-secret-webhook-token"

    def when_token_is_validated(self):
        self.result = validate_webhook_token(self.token, self.secret)

    def then_it_should_return_true(self):
        assert self.result is True
