"""Test _process_mr returns ERROR on unexpected exception.

When state_machine_factory raises an unexpected RuntimeError,
_process_mr should catch it and return ProcessingResult.ERROR instead
of letting the exception propagate and crash the processing loop.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_test_queue_item,
)


async def _error_factory(*args, **kwargs):
    raise RuntimeError("boom")


class Scenario(vedro.Scenario):
    subject = "process mr returns error on unexpected exception"

    def given_processor_with_create_state_machine_raising_runtime_error(self):
        self.processor = create_mock_processor(state_machine_factory=_error_factory)
        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")

    async def when_process_mr_is_called(self):
        self.result = await self.processor._process_mr(self.queue_item)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR
