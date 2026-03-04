"""Test _maybe_rebase_during_testing returns outcome with ProcessingResult when check returns error.

Line 948: when _check_and_handle_rebase_during_testing returns a ProcessingResult
(not None and not RebaseDuringTestingContext), return RebaseCheckOutcome with that result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import vedro

from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.rebase_coordinator import maybe_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "maybe_rebase_during_testing returns outcome with ProcessingResult when check returns error"

    def given_processor_where_rebase_check_returns_processing_result(self):
        self.processor = create_mock_processor(
            settings=create_mock_settings(
                rebase_check_interval_seconds=0,  # Always check
            )
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3, current_pipeline_id=100)

        self.last_rebase_check = datetime(2020, 1, 1, tzinfo=UTC)  # Old timestamp → will check

    async def when_maybe_rebase_during_testing_is_called(self):
        state = create_pipeline_wait_state(
            rebase_ctx=self.rebase_ctx,
            last_rebase_check=self.last_rebase_check,
        )
        with patch(
            "gitlab_queue.core.rebase_coordinator.check_and_handle_rebase_during_testing",
            new_callable=AsyncMock,
            return_value=ProcessingResult.CONFLICT,
        ):
            self.outcome = await maybe_rebase_during_testing(
                settings=self.processor.settings,
                ctx=self.ctx,
                state=state,
                pipeline=self.pipeline,
            )

    def then_outcome_result_is_conflict(self):
        assert self.outcome.result == ProcessingResult.CONFLICT

    def and_outcome_context_is_none(self):
        assert self.outcome.context is None

    def and_outcome_should_reset_is_false(self):
        assert self.outcome.should_reset is False
