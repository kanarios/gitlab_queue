"""Test check_rebase_status detects rebase failure via merge_error field.

GitLab can report a failed rebase through the merge_error field while
has_conflicts remains False. This happens when rebase encounters conflicts
but GitLab doesn't update the has_conflicts flag. The bot must detect
"Rebase failed" in merge_error and treat it as a conflict.

Without the fix: has_conflicts=False → bot thinks rebase succeeded → merge fails.
With the fix: merge_error="Rebase failed: ..." → treated as conflict → CONFLICT result.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase returns CONFLICT when merge_error indicates rebase failure"

    def given_processor_with_rebase_failure_in_merge_error(self):
        self.processor = create_mock_processor()

        # GitLab returns has_conflicts=False but merge_error indicates rebase failed
        self.processor.gitlab_client.mr_responses = {
            42: create_mr(
                iid=42,
                sha="abc123",
                has_conflicts=False,
                rebase_in_progress=False,
                merge_error="Rebase failed: Rebase locally, resolve all conflicts, then push the branch. Try again.",
            ),
        }
        self.processor.gitlab_client.mr_conflicts = ["README.md"]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.ctx.rebase_ctx.old_sha = "abc123"

    async def when_wait_for_rebase_is_called(self):
        self.result = await self.processor._rebase_handler.wait_for_rebase(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def then_trigger_rebase_failed_was_called(self):
        assert len(self.mock_sm.rebase_failed_calls) == 1

    def then_error_message_contains_gitlab_merge_error(self):
        error_msg = self.mock_sm.rebase_failed_calls[0]["error_message"]
        assert "Rebase locally, resolve all conflicts" in error_msg
