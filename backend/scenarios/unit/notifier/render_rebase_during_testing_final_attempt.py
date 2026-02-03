"""Test _render_template() with rebase_during_testing status on final attempt."""

from __future__ import annotations

import vedro

from ._helpers import create_test_notifier


class Scenario(vedro.Scenario):
    subject = "_render_template() with rebase_during_testing appends final attempt warning when rebase_count equals max_attempts"

    def given_notifier_and_final_attempt_context(self):
        self.notifier = create_test_notifier()
        self.rebase_count = 3
        self.max_attempts = 3

    def when_render_template_is_called_for_rebase_during_testing(self):
        self.result = self.notifier._render_template(
            "rebase_during_testing",
            rebase_count=self.rebase_count,
            max_attempts=self.max_attempts,
            pipeline_id=99,
            pipeline_url="http://gitlab.example.com/pipelines/99",
        )

    def then_result_contains_final_attempt_warning(self):
        assert "Final attempt" in self.result

    def and_result_contains_rebase_count_and_max(self):
        assert f"{self.rebase_count}/{self.max_attempts}" in self.result

    def and_result_contains_pipeline_id(self):
        assert "99" in self.result
