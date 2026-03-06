"""Test _wait_for_rebase returns ERROR when poll_outcome is not completed/shutdown/timeout.

Line 474: defensive fallback return ProcessingResult.ERROR when poll_until_done
returns completed=True but result is falsy (e.g. None).
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.polling import PollOutcome
from gitlab_queue.core.types import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase returns ERROR when poll completes with falsy result"

    def given_processor_where_poll_returns_completed_false_result(self):
        # Simulate poll_until_done completing with result=None (falsy)
        # This hits the defensive fallback at line 474
        self.fake_outcome = PollOutcome(
            completed=True,
            timed_out=False,
            shutdown_requested=False,
            result=None,
        )

        async def fake_poll_fn(config, fn, shutdown_event, **kwargs):
            return self.fake_outcome

        self.processor = create_mock_processor(
            settings=create_mock_settings(rebase_timeout_seconds=60),
            poll_fn=fake_poll_fn,
        )
        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_wait_for_rebase_is_called(self):
        self.result = await self.processor._wait_for_rebase(self.ctx)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR
