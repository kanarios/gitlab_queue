"""Test _maybe_rebase_during_testing returns outcome with should_reset=True when new pipeline found.

Lines 932-948: when _check_and_handle_rebase_during_testing returns a context with new pipeline_id,
the outcome has should_reset=True.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.rebase_coordinator import maybe_rebase_during_testing
from gitlab_queue.core.rebase_during_testing import RebaseDuringTestingContext
from scenarios.fakes import FakeRebaseDuringTestingHandler, create_pipeline

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "maybe_rebase_during_testing returns outcome with should_reset True when new pipeline"

    def given_processor_where_rebase_produces_new_pipeline(self):
        self.processor = create_mock_processor(
            settings=create_mock_settings(
                rebase_check_interval_seconds=0,  # Always check
            )
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")

        # Initial context: pipeline_id=100
        self.rebase_ctx = RebaseDuringTestingContext(rebase_count=0, max_attempts=3, current_pipeline_id=100)

        # New context after rebase: pipeline_id=200 (changed!)
        self.new_rebase_ctx = RebaseDuringTestingContext(rebase_count=1, max_attempts=3, current_pipeline_id=200)

        # Handler returns (new_ctx, new_pipeline) → rebase happened with new pipeline
        new_pipeline = create_pipeline(id=200, sha="new_sha", status="running")
        self.rebase_handler = FakeRebaseDuringTestingHandler(
            result=(self.new_rebase_ctx, new_pipeline),
            gitlab_client=self.processor.gitlab_client,
        )

        self.last_rebase_check = datetime(2020, 1, 1, tzinfo=UTC)  # Old timestamp → will check

    async def when_maybe_rebase_during_testing_is_called(self):
        state = create_pipeline_wait_state(
            rebase_handler=self.rebase_handler,
            rebase_ctx=self.rebase_ctx,
            last_rebase_check=self.last_rebase_check,
        )
        self.outcome = await maybe_rebase_during_testing(
            settings=self.processor.settings,
            ctx=self.ctx,
            state=state,
            pipeline=self.pipeline,
        )

    def then_outcome_has_should_reset_true(self):
        assert self.outcome.should_reset is True

    def and_outcome_has_updated_context(self):
        assert self.outcome.context is self.new_rebase_ctx

    def and_outcome_result_is_none(self):
        assert self.outcome.result is None
