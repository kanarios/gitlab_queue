"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret length returns correct value"

    def given_secret_with_known_length(self):
        self.value = "12345678"
        self.secret = Secret(self.value)

    def when_getting_length(self):
        self.length = len(self.secret)

    def then_it_should_return_correct_length(self):
        assert self.length == 8
