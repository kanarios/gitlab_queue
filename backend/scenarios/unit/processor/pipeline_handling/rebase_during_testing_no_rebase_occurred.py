"""Test _check_and_handle_rebase_during_testing returns None when rebase count unchanged.

Line 1087: when handle_rebase_if_needed returns (new_ctx, None) with same rebase_count
(no actual rebase occurred), return None to indicate no change.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.rebase_coordinator import check_and_handle_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "check_and_handle_rebase_during_testing returns None when rebase count unchanged"

    def given_processor_where_handle_rebase_returns_same_count(self):
        self.processor = create_mock_processor()
        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=1, max_attempts=3, current_pipeline_id=100)

        # Same rebase_count as rebase_ctx — no actual rebase occurred
        self.same_count_ctx = RebaseDuringTestingContext(
            rebase_count=1,  # Same as rebase_ctx.rebase_count
            max_attempts=3,
            current_pipeline_id=100,
        )

        # Mock rebase_handler: returns (same_count_ctx, None) — no new pipeline
        self.mock_handler = MagicMock()
        self.mock_handler.handle_rebase_if_needed = AsyncMock(return_value=(self.same_count_ctx, None))

    async def when_check_and_handle_rebase_during_testing_is_called(self):
        state = create_pipeline_wait_state(
            rebase_handler=self.mock_handler,
            rebase_ctx=self.rebase_ctx,
        )
        self.result = await check_and_handle_rebase_during_testing(
            gitlab_client=self.processor.gitlab_client,
            ctx=self.ctx,
            state=state,
            pipeline=self.pipeline,
        )

    def then_result_is_none(self):
        assert self.result is None

    def and_notify_was_not_called(self):
        self.mock_sm.notify_rebase_during_testing.assert_not_called()
