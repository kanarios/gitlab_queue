"""Test _check_and_handle_rebase_during_testing returns CONFLICT on GitLabConflictError.

When handle_rebase_if_needed raises GitLabConflictError because the rebase
encountered merge conflicts, the handler should trigger_rebase_failed and
return ProcessingResult.CONFLICT.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "rebase during testing returns conflict on conflict error"

    def given_processor_with_rebase_conflict_during_testing(self):
        """
        Set up a processor and supporting mocks to simulate a rebase conflict occurring during testing.

        Creates:
        - a mock processor,
        - a mock state machine and a processing context with mr_iid=42,
        - a RebaseDuringTestingContext with rebase_count=0 and max_attempts=3,
        - a mock pipeline (pipeline_id=100, sha="abc123", status="running"),
        - a rebase_handler whose handle_rebase_if_needed raises GitLabConflictError("MR has conflicts during testing"),
        and configures processor.gitlab_client.get_mr_conflicts to return ["file1.py"].
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_handler = MagicMock()
        self.rebase_handler.handle_rebase_if_needed = AsyncMock(
            side_effect=GitLabConflictError("MR has conflicts during testing")
        )

        # get_mr_conflicts is called when GitLabConflictError is caught
        self.processor.gitlab_client.get_mr_conflicts.return_value = [
            "file1.py",
        ]

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        """
        Invokes the processor's rebase-check routine with the prepared context and saves the resulting ProcessingResult to self.result.
        """
        self.result = await self.processor._check_and_handle_rebase_during_testing(
            ctx=self.ctx,
            sm=self.mock_sm,
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            pipeline=self.pipeline,
            retry_count=0,
        )

    def then_result_is_conflict(self):
        """
        Asserts that the processing result indicates a conflict.

        Raises:
            AssertionError: If `self.result` is not `ProcessingResult.CONFLICT`.
        """
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_conflict_during_testing_was_called(self):
        self.mock_sm.trigger_conflict_during_testing.assert_awaited_once()
