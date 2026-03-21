"""Test that externally merged MR during pipeline wait triggers external_merge reason."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
)


class Scenario(vedro.Scenario):
    subject = "externally merged MR during pipeline wait triggers external_merge reason"

    def given_pipeline_handler_with_externally_merged_mr(self):
        self.handler = create_test_pipeline_handler()

        # MR is merged externally — still has the label
        self.handler.gitlab_client.mr_responses[42] = create_mr(iid=42, state="merged", labels=["merge_queue"])

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.timeout = timedelta(seconds=3600)
        self.start_time = datetime.now(UTC)

    async def when_check_pipeline_termination_conditions_is_called(self):
        self.result = await self.handler.check_pipeline_termination_conditions(
            ctx=self.ctx,
            sm=self.mock_sm,
            timeout=self.timeout,
            start_time=self.start_time,
        )

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def then_reason_is_external_merge(self):
        assert len(self.mock_sm.mark_removed_calls) == 1
        assert self.mock_sm.mark_removed_calls[0]["reason"] == "external_merge"
