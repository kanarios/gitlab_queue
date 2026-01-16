"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret equality uses constant-time comparison"

    def given_two_equal_secrets(self):
        value = fake(SecretValueSchema)
        self.secret1 = Secret(value)
        self.secret2 = Secret(value)

    def when_comparing_secrets(self):
        self.result = self.secret1 == self.secret2

    def then_they_should_be_equal(self):
        assert self.result is True
