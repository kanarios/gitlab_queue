"""Test _sync_missing_mrs_from_gitlab returns on GitLabCircuitOpenError.

When list_mrs_with_label raises GitLabCircuitOpenError (circuit breaker
is open), the sync method should return gracefully without raising an
exception, allowing the processor to continue startup.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError

from .._helpers import create_mock_processor


class Scenario(vedro.Scenario):
    subject = "sync missing mrs from gitlab skips when circuit open"

    def given_processor_with_circuit_open(self):
        self.processor = create_mock_processor()
        self.processor.gitlab_client.list_mrs_with_label.side_effect = GitLabCircuitOpenError(
            "Circuit open", retry_after=30
        )

    async def when_sync_missing_mrs_from_gitlab_is_called(self):
        self.raised = None
        try:
            await self.processor._sync_missing_mrs_from_gitlab()
        except Exception as exc:
            self.raised = exc

    def then_no_error_is_raised(self):
        assert self.raised is None
