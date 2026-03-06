"""Test _recover_interrupted_state removes MR when GitLab returns 404.

When the processor restarts and GitLab reports the MR as not found,
the MR should be marked as 'removed' in the queue.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabNotFoundError

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "recover interrupted state removes MR on GitLab not found"

    def given_processor_with_nonexistent_mr_in_queue(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.add_item(self.queue_item)

        self.processor.gitlab_client.get_mr_error = GitLabNotFoundError("MR not found", status_code=404)

    async def when_recover_interrupted_state_is_called(self):
        """
        Invoke the processor's interrupted-state recovery routine to exercise recovery behavior with the configured test fixtures.
        """
        await self.processor._recover_interrupted_state()

    def then_mr_is_marked_as_removed(self):
        assert len(self.processor.queue_manager.complete_calls) == 1
        call = self.processor.queue_manager.complete_calls[0]
        assert call["mr_iid"] == 42
        assert call["status"] == "removed"
        assert call["failure_reason"] == "not_found"
