"""Test _format_file_list() truncates lists longer than 10 items."""

from __future__ import annotations

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "_format_file_list() truncates list to 10 items and appends overflow note"

    def given_notifier_and_twelve_files(self):
        self.notifier = create_test_notifier()
        self.files = [f"src/file_{i}.py" for i in range(1, 13)]

    def when_format_file_list_is_called_with_long_list(self):
        self.result = self.notifier._format_file_list(self.files)

    def then_result_lists_exactly_ten_files(self):
        file_lines = [line for line in self.result.splitlines() if line.startswith("- `")]
        assert len(file_lines) == 10

    def and_result_contains_overflow_note_for_remaining_two(self):
        assert "...and 2 more" in self.result

    def and_first_file_appears_in_result(self):
        assert "src/file_1.py" in self.result

    def and_eleventh_file_does_not_appear_directly(self):
        assert "- `src/file_11.py`" not in self.result
