"""Test _wait_for_pipeline sleeps and continues when _handle_pipeline_status returns None.

Lines 830-831: when _handle_pipeline_status returns None (no action needed), sleep and continue.
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
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_pipeline sleeps and continues when handle_pipeline_status returns None"

    def given_processor_where_handle_status_returns_none_then_removed(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="running")
        self.processor.gitlab_client.latest_pipeline_response = self.pipeline

        queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.add_item(queue_item)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.termination_call_count = 0
        self.status_call_count = 0
        self.sleep_call_count = 0

        self.no_result_rebase = RebaseCheckOutcome(
            context=None, result=None, last_check=datetime.now(UTC), should_reset=False
        )

    async def when_wait_for_pipeline_is_called(self):
        handler = self.processor._pipeline_handler

        async def termination_side_effect(_ctx, _sm, _timeout, _start):
            self.termination_call_count += 1
            if self.termination_call_count >= 2:
                return ProcessingResult.REMOVED
            return None

        async def status_side_effect(_ctx, _sm, _pipeline, _retried_jobs):
            self.status_call_count += 1
            return None  # Continue polling

        async def fake_sleep(seconds):
            self.sleep_call_count += 1
            return True

        async def fake_skip(_mr_iid, _pipeline):
            return False

        handler.check_pipeline_termination_conditions = termination_side_effect
        handler.should_skip_stale_pipeline = fake_skip
        handler.handle_pipeline_status = status_side_effect
        handler._interruptible_sleep = fake_sleep

        async def fake_rebase(*args, **kwargs):
            return self.no_result_rebase

        original = _ph_mod.maybe_rebase_during_testing
        _ph_mod.maybe_rebase_during_testing = fake_rebase
        try:
            self.result = await self.processor._wait_for_pipeline(self.ctx)
        finally:
            _ph_mod.maybe_rebase_during_testing = original

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_handle_pipeline_status_returned_none(self):
        assert self.status_call_count >= 1

    def and_sleep_was_called(self):
        assert self.sleep_call_count >= 1
