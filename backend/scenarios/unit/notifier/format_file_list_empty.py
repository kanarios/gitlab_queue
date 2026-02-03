"""Test _format_file_list() returns unknown files placeholder for empty list."""

from __future__ import annotations

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "_format_file_list() returns '_(unknown files)_' for empty list"

    def given_notifier_and_empty_file_list(self):
        self.notifier = create_test_notifier()
        self.files = []

    def when_format_file_list_is_called_with_empty_list(self):
        self.result = self.notifier._format_file_list(self.files)

    def then_result_is_unknown_files_placeholder(self):
        assert self.result == "_(unknown files)_"
