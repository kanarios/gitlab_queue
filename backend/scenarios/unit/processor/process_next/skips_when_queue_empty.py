"""Test _process_iteration returns early when queue is empty.

When get_next_mr returns None, the processor should log that the queue
is empty and return without calling _process_mr.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "process iteration returns early when queue is empty"

    def given_processor_with_empty_queue(self):
        self.processor = create_mock_processor()
        # Queue is empty by default in FakeQueueManager

    async def when_process_iteration_is_called(self):
        await self.processor._process_iteration()

    def then_no_mr_was_processed(self):
        # If _process_mr was called, it would have called gitlab_client methods
        assert self.processor.gitlab_client.rebase_calls == []
        assert self.processor.gitlab_client.merge_calls == []
