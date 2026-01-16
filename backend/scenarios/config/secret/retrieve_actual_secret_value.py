"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "retrieve actual secret value"

    def given_secret(self):
        self.secret_value = fake(SecretValueSchema)
        self.secret = Secret(self.secret_value)

    def when_getting_secret_value(self):
        self.retrieved = self.secret.get_secret_value()

    def then_it_should_return_original_value(self):
        assert self.retrieved == self.secret_value
