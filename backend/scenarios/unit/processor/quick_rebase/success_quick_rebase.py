"""Test _wait_for_rebase_quick returns None (success) when rebase completes without conflicts.

Line 1162: when check_rebase_status returns (False, False) (done, no conflicts), return normally.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase_quick returns successfully when rebase completes without conflicts"

    def given_processor_with_successful_quick_rebase(self):
        self.processor = create_mock_processor()

        # check_rebase_status returns (False, False) = done, no conflicts
        self.processor.gitlab_client.check_rebase_status.return_value = (False, False)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_wait_for_rebase_quick_is_called(self):
        self.exception = None
        try:
            self.result = await self.processor._rebase_handler.wait_for_rebase_quick(self.ctx)
        except Exception as e:
            self.exception = e

    def then_no_exception_is_raised(self):
        assert self.exception is None

    def and_check_rebase_status_was_called(self):
        self.processor.gitlab_client.check_rebase_status.assert_awaited()
