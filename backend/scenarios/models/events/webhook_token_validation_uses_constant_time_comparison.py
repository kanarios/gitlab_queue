"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import validate_webhook_token


class Scenario(vedro.Scenario):
    subject = "webhook token validation uses constant-time comparison"

    def given_tokens_with_common_prefix(self):
        self.token1 = "secret-token-123"
        self.token2 = "secret-token-456"
        self.secret = "secret-token-789"

    def when_validating_both_tokens(self):
        self.result1 = validate_webhook_token(self.token1, self.secret)
        self.result2 = validate_webhook_token(self.token2, self.secret)

    def then_both_should_fail(self):
        assert self.result1 is False
        assert self.result2 is False
