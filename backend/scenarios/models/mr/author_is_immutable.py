"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author


class Scenario(vedro.Scenario):
    subject = "author is immutable (frozen)"

    def given_author(self):
        self.author = Author(id=1, name="Test", username="test")

    def when_trying_to_modify_author(self):
        try:
            self.author.name = "New Name"
            self.error = None
        except Exception as e:
            self.error = e

    def then_it_should_raise_frozen_error(self):
        assert self.error is not None
        assert "frozen" in str(type(self.error).__name__).lower() or "cannot" in str(self.error).lower()
