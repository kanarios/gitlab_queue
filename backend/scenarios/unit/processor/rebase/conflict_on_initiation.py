"""Test _process_rebase returns CONFLICT when rebase_mr raises GitLabConflictError.

Lines 382-390: when rebase_mr raises GitLabConflictError on initiation,
trigger_rebase_failed and return CONFLICT.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "process rebase returns CONFLICT when rebase_mr raises conflict on initiation"

    def given_processor_with_conflict_on_rebase_initiation(self):
        self.processor = create_mock_processor()

        mock_mr = create_mock_mr(iid=42, sha="abc123")
        self.processor.gitlab_client.get_mr.return_value = mock_mr

        self.processor.gitlab_client.rebase_mr.side_effect = GitLabConflictError("Rebase conflict: cannot rebase")
        self.processor.gitlab_client.get_mr_conflicts.return_value = ["src/file.py"]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.processor._process_rebase(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_rebase_failed_was_called(self):
        self.mock_sm.trigger_rebase_failed.assert_awaited_once()

    def and_get_mr_conflicts_was_called(self):
        self.processor.gitlab_client.get_mr_conflicts.assert_awaited_once_with(42)
