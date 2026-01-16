"""Unit tests for webhook event models."""

import vedro

from gitlab_queue.models.events import LabelChanges


class Scenario(vedro.Scenario):
    subject = "detect removed label"

    def given_label_changes_with_removal(self):
        self.changes = LabelChanges(
            previous=["feature", "merge_queue"],
            current=["feature"],
        )

    def when_removed_labels_are_calculated(self):
        self.removed = set(self.changes.previous) - set(self.changes.current)

    def then_it_should_detect_removed_label(self):
        assert "merge_queue" in self.removed
