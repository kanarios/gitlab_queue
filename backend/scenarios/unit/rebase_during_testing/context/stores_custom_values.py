"""Test RebaseDuringTestingContext stores custom values correctly."""

import vedro

from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext


class Scenario(vedro.Scenario):
    subject = "RebaseDuringTestingContext stores custom values correctly"

    def given_custom_values(self):
        self.rebase_count = 2
        self.max_attempts = 5
        self.current_pipeline_id = 12345

    def when_context_is_created(self):
        self.ctx = RebaseDuringTestingContext(
            rebase_count=self.rebase_count,
            max_attempts=self.max_attempts,
            current_pipeline_id=self.current_pipeline_id,
        )

    def then_rebase_count_matches(self):
        assert self.ctx.rebase_count == self.rebase_count

    def and_max_attempts_matches(self):
        assert self.ctx.max_attempts == self.max_attempts

    def and_current_pipeline_id_matches(self):
        assert self.ctx.current_pipeline_id == self.current_pipeline_id
