"""Test _format_job_list() truncates lists longer than 10 items."""

from __future__ import annotations

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "_format_job_list() truncates list to 10 items and appends overflow note"

    def given_notifier_and_fifteen_jobs(self):
        self.notifier = create_test_notifier()
        self.jobs = [f"test:job-{i}" for i in range(1, 16)]

    def when_format_job_list_is_called_with_long_list(self):
        self.result = self.notifier._format_job_list(self.jobs)

    def then_result_lists_exactly_ten_jobs(self):
        job_lines = [line for line in self.result.splitlines() if line.startswith("- test:")]
        assert len(job_lines) == 10

    def and_result_contains_overflow_note_for_remaining_five(self):
        assert "...and 5 more" in self.result

    def and_first_job_appears_in_result(self):
        assert "test:job-1" in self.result

    def and_eleventh_job_does_not_appear_directly(self):
        assert "- test:job-11" not in self.result
