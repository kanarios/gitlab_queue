"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secrets with same value have same hash"

    def given_two_secrets_with_same_value(self):
        self.secret1 = Secret("identical")
        self.secret2 = Secret("identical")

    def when_getting_hashes(self):
        self.hash1 = hash(self.secret1)
        self.hash2 = hash(self.secret2)

    def then_hashes_should_be_equal(self):
        assert self.hash1 == self.hash2
