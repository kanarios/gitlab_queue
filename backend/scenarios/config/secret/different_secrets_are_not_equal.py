"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "different secrets are not equal"

    def given_two_different_secrets(self):
        self.secret1 = Secret(fake(SecretValueSchema))
        self.secret2 = Secret(fake(SecretValueSchema))

    def when_comparing_two_different_secrets(self):
        self.result = self.secret1 == self.secret2

    def then_they_should_not_be_equal(self):
        assert self.result is False
