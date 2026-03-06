"""Test _wait_for_rebase_quick raises GitLabConflictError when rebase has conflicts.

Lines 1145-1148: when check_rebase_status returns (False, True), capture the conflict error.
After poll completes, raise the captured GitLabConflictError.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase_quick raises GitLabConflictError when rebase has conflicts"

    def given_processor_with_conflict_during_quick_rebase(self):
        self.processor = create_mock_processor()

        # check_rebase_status returns (False, True) = not in progress, has conflicts
        self.processor.gitlab_client.check_rebase_status.return_value = (False, True)
        self.processor.gitlab_client.get_mr_conflicts.return_value = ["file.py"]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_wait_for_rebase_quick_is_called(self):
        self.exception = None
        try:
            await self.processor._rebase_handler.wait_for_rebase_quick(self.ctx)
        except GitLabConflictError as e:
            self.exception = e

    def then_conflict_error_is_raised(self):
        assert self.exception is not None
        assert isinstance(self.exception, GitLabConflictError)

    def and_conflicts_file_is_mentioned(self):
        assert "file.py" in str(self.exception)
