"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secrets with same value have same hash"

    def given_two_secrets_with_same_value(self):
        value = fake(SecretValueSchema)
        self.secret1 = Secret(value)
        self.secret2 = Secret(value)

    def when_getting_hashes(self):
        self.hash1 = hash(self.secret1)
        self.hash2 = hash(self.secret2)

    def then_hashes_should_be_equal(self):
        assert self.hash1 == self.hash2
