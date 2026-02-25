"""Test _recover_interrupted_state handles database errors gracefully.

When get_active_queue raises an exception (e.g. database connection
failure), _recover_interrupted_state should catch the error and return
without crashing the processor startup sequence.
"""

from __future__ import annotations

import vedro

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "recover interrupted state handles database error gracefully"

    def given_processor_with_database_error(self):
        """
        Configure a mock processor that simulates a database error when retrieving the active queue.
        
        Sets self.processor to a mock processor and configures its queue_manager.get_active_queue to raise Exception("DB error") when invoked.
        """
        self.processor = create_mock_processor()
        self.processor.queue_manager.get_active_queue.side_effect = Exception("DB error")

    async def when_recover_interrupted_state_is_called(self):
        self.raised = None
        try:
            await self.processor._recover_interrupted_state()
        except Exception as exc:
            self.raised = exc

    def then_no_error_is_raised(self):
        """
        Asserts that the recovery operation did not raise an exception.
        
        Raises:
            AssertionError: If an exception was captured during recovery.
        """
        assert self.raised is None
