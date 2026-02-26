"""Test: pipeline_retry template shows 'last retry' only on final attempt."""

from __future__ import annotations

import vedro

from ._helpers import create_test_notifier


class Scenario__not_last_attempt(vedro.Scenario):
    subject = "pipeline_retry does NOT show 'last retry' when retry_count < max_retries"

    def given_notifier(self):
        self.notifier = create_test_notifier()

    def when_template_is_rendered(self):
        self.result = self.notifier._render_template(
            "pipeline_retry",
            retry_count=1,
            max_retries=3,
            old_pipeline_id=100,
            old_pipeline_url="https://gitlab.com/pipeline/100",
            pipeline_id=200,
            pipeline_url="https://gitlab.com/pipeline/200",
            failed_jobs=["test_job"],
        )

    def then_result_should_not_contain_last_retry(self):
        assert "last retry" not in self.result.lower(), (
            f"Expected no 'last retry' text, but found it in:\n{self.result}"
        )


class Scenario__last_attempt(vedro.Scenario):
    subject = "pipeline_retry shows 'last retry' when retry_count == max_retries"

    def given_notifier(self):
        self.notifier = create_test_notifier()

    def when_template_is_rendered(self):
        self.result = self.notifier._render_template(
            "pipeline_retry",
            retry_count=3,
            max_retries=3,
            old_pipeline_id=100,
            old_pipeline_url="https://gitlab.com/pipeline/100",
            pipeline_id=200,
            pipeline_url="https://gitlab.com/pipeline/200",
            failed_jobs=["test_job"],
        )

    def then_result_should_contain_last_retry(self):
        assert "last retry" in self.result.lower(), f"Expected 'last retry' text, but not found in:\n{self.result}"
