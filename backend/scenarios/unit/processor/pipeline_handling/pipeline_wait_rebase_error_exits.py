"""Test _wait_for_pipeline returns result when _maybe_rebase_during_testing returns a result.

Line 809: when outcome.result is not None, return from the loop immediately.
"""

from __future__ import annotations

from datetime import UTC, datetime

import vedro

import gitlab_queue.core.pipeline_handler as _ph_mod
from gitlab_queue.core.processor import ProcessingResult
from gitlab_queue.core.types import RebaseCheckOutcome

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_pipeline exits loop when maybe_rebase_during_testing returns result"

    def given_processor_with_rebase_conflict_during_testing(self):
        self.processor = create_mock_processor()

        # Pipeline exists
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        self.processor.gitlab_client.latest_pipeline_response = self.pipeline

        queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.add_item(queue_item)

        # _maybe_rebase_during_testing returns a conflict result
        self.conflict_outcome = RebaseCheckOutcome(
            context=None,
            result=ProcessingResult.CONFLICT,
            last_check=datetime.now(UTC),
            should_reset=False,
        )

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_wait_for_pipeline_is_called(self):
        handler = self.processor._pipeline_handler

        async def fake_termination(*args, **kwargs):
            return None

        handler.check_pipeline_termination_conditions = fake_termination

        async def fake_rebase(*args, **kwargs):
            return self.conflict_outcome

        self._original_rebase = _ph_mod.maybe_rebase_during_testing
        _ph_mod.maybe_rebase_during_testing = fake_rebase
        try:
            self.result = await self.processor._wait_for_pipeline(self.ctx)
        finally:
            _ph_mod.maybe_rebase_during_testing = self._original_rebase

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT
