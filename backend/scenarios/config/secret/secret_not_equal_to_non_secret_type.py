"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret not equal to non-secret type"

    def given_secret_and_string(self):
        value = fake(SecretValueSchema)
        self.secret = Secret(value)
        self.string = value

    def when_comparing_secret_to_string(self):
        self.result = self.secret == self.string

    def then_they_should_not_be_equal(self):
        # When Secret.__eq__ returns NotImplemented for non-Secret types,
        # Python falls back to identity comparison which returns False
        assert self.result is False
