"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret is hashable"

    def given_secret(self):
        self.secret = Secret(fake(SecretValueSchema))

    def when_getting_hash(self):
        self.hash_value = hash(self.secret)

    def then_it_should_return_hash(self):
        assert isinstance(self.hash_value, int)
