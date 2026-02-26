"""Test _extract_labels() is robust to mixed label formats."""

from __future__ import annotations

import vedro

from gitlab_queue.models.retorts import _extract_labels


class Scenario(vedro.Scenario):
    subject = "_extract_labels() handles mixed types and drops invalid labels"

    def given_labels_with_mixed_types_and_invalid_values(self):
        self.labels = [
            {"title": "merge_queue"},
            "hotfix",
            {},  # missing keys
            {"name": "bug"},
            {"title": "   "},  # blank should be dropped
            None,  # type: ignore[list-item]
        ]

    def when_extract_labels_is_called(self):
        self.result = _extract_labels(self.labels)  # type: ignore[arg-type]

    def then_only_valid_non_empty_labels_are_returned(self):
        assert self.result == ["merge_queue", "hotfix", "bug"]
