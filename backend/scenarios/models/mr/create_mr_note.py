"""Unit tests for MergeRequest and Author models."""

import vedro

from gitlab_queue.models.mr import Author, Note


class Scenario(vedro.Scenario):
    subject = "create MR note"

    def given_note_data(self):
        self.author = Author(id=42, name="Bot", username="merge-queue-bot")

    def when_note_is_created(self):
        self.note = Note(
            id=999,
            body="Pipeline started: https://gitlab.com/pipeline/123",
            author=self.author,
            system=False,
        )

    def then_it_should_have_correct_fields(self):
        assert self.note.id == 999
        assert "Pipeline started" in self.note.body
        assert self.note.author == self.author
        assert self.note.system is False
