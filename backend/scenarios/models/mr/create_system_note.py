"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, Note


class Scenario(vedro.Scenario):
    subject = "create system note"

    def given_system_author(self):
        self.author = Author(id=0, name="GitLab", username="gitlab")

    def when_system_note_is_created(self):
        self.note = Note(
            id=1000,
            body="changed the description",
            author=self.author,
            system=True,
        )

    def then_it_should_be_marked_as_system(self):
        assert self.note.system is True
