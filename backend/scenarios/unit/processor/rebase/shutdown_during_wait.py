"""Test _wait_for_rebase returns ERROR when shutdown is requested during polling.

Lines 460-462: when shutdown event is set, return ProcessingResult.ERROR.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase returns ERROR when shutdown is requested"

    def given_processor_with_shutdown_event_set(self):
        self.processor = create_mock_processor(settings=create_mock_settings(rebase_timeout_seconds=60))
        # Rebase in progress — would keep polling, but shutdown stops it
        self.processor.gitlab_client.rebase_status = (True, False)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.ctx.rebase_ctx.old_sha = "abc123"

        # Set shutdown BEFORE calling so poll_until_done sees it immediately
        self.processor._shutdown_event.set()

    async def when_wait_for_rebase_is_called(self):
        self.result = await self.processor._wait_for_rebase(self.ctx)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def and_trigger_timeout_was_not_called(self):
        assert len(self.mock_sm.timeout_calls) == 0
