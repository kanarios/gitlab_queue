"""Test _check_pipeline_termination_conditions returns ERROR when shutdown is requested.

Lines 853-854: when _shutdown_event is set, return ProcessingResult.ERROR.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "check_pipeline_termination_conditions returns ERROR when shutdown requested"

    def given_processor_with_shutdown_event_set(self):
        self.processor = create_mock_processor()
        self.processor._shutdown_event.set()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.timeout = timedelta(seconds=3600)
        self.start_time = datetime.now(UTC)

    async def when_check_pipeline_termination_conditions_is_called(self):
        self.result = await self.processor._pipeline_handler.check_pipeline_termination_conditions(
            ctx=self.ctx,
            sm=self.mock_sm,
            timeout=self.timeout,
            start_time=self.start_time,
        )

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR
