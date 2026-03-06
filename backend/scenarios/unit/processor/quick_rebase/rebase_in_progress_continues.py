"""Test _wait_for_rebase_quick continues polling when rebase is in progress.

Line 1148: when check_rebase_status returns (True, False) — rebase still in progress,
no conflicts — return PollStatus.CONTINUE so polling continues.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase_quick continues when rebase is in progress"

    def given_processor_where_rebase_first_in_progress_then_done(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Override check_rebase_status to return sequential values
        self.rebase_status_sequence = [
            (True, False),  # In progress → CONTINUE
            (False, False),  # Done, no conflicts → success
        ]
        self.check_rebase_call_count = 0

        original_client = self.processor.gitlab_client

        async def sequential_check_rebase_status(iid):
            idx = min(self.check_rebase_call_count, len(self.rebase_status_sequence) - 1)
            self.check_rebase_call_count += 1
            return self.rebase_status_sequence[idx]

        original_client.check_rebase_status = sequential_check_rebase_status

    async def when_wait_for_rebase_quick_is_called(self):
        # Should complete successfully without raising
        self.exception = None
        try:
            await self.processor._rebase_handler.wait_for_rebase_quick(self.ctx)
        except Exception as e:
            self.exception = e

    def then_no_exception_was_raised(self):
        assert self.exception is None

    def and_check_rebase_status_was_called_twice(self):
        assert self.check_rebase_call_count == 2
