"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import LabelChanges


class Scenario(vedro.Scenario):
    subject = "create label changes"

    def when_label_changes_are_created(self):
        self.changes = LabelChanges(
            previous=["feature"],
            current=["feature", "merge_queue"],
        )

    def then_it_should_have_correct_labels(self):
        assert self.changes.previous == ["feature"]
        assert self.changes.current == ["feature", "merge_queue"]

    def and_added_label_can_be_detected(self):
        added = set(self.changes.current) - set(self.changes.previous)
        assert "merge_queue" in added
