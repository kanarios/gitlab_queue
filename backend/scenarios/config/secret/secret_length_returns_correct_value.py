"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret length returns correct value"

    def given_secret_with_known_length(self):
        self.value = fake(SecretValueSchema)
        self.secret = Secret(self.value)

    def when_getting_length(self):
        self.length = len(self.secret)

    def then_it_should_return_correct_length(self):
        assert self.length == len(self.value)
