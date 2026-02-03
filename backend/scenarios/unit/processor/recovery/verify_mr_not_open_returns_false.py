"""Test _verify_mr_in_queue returns False when MR state is closed.

When the MR retrieved from GitLab has state "closed" instead of "opened",
_verify_mr_in_queue should return False, indicating the MR is no longer
valid for processing in the merge queue.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
)


class Scenario(vedro.Scenario):
    subject = "verify mr in queue returns false when mr is closed"

    def given_processor_with_closed_mr(self):
        self.processor = create_mock_processor()

        self.mock_mr = create_mock_mr(iid=42, state="closed", labels=["merge_queue"])
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

    async def when_verify_mr_in_queue_is_called(self):
        self.result = await self.processor._verify_mr_in_queue(42)

    def then_result_is_false(self):
        assert self.result is False
