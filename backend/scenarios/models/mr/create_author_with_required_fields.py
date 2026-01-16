"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author


class Scenario(vedro.Scenario):
    subject = "create author with required fields"

    def given_author_data(self):
        self.author_id = 42
        self.name = "John Doe"
        self.username = "johndoe"

    def when_author_is_created(self):
        self.author = Author(
            id=self.author_id,
            name=self.name,
            username=self.username,
        )

    def then_it_should_have_correct_fields(self):
        assert self.author.id == self.author_id
        assert self.author.name == self.name
        assert self.author.username == self.username
        assert self.author.avatar_url is None
