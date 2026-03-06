"""Test _wait_for_pipeline sleeps and continues when _handle_pipeline_status returns None.

Lines 830-831: when _handle_pipeline_status returns None (no action needed), sleep and continue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import vedro

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
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = self.pipeline

        queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_queue_item.return_value = queue_item

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.termination_call_count = 0
        self.status_call_count = 0

        no_result_rebase = RebaseCheckOutcome(
            context=None, result=None, last_check=datetime.now(UTC), should_reset=False
        )

        async def termination_side_effect(_ctx, _sm, _timeout, _start):
            self.termination_call_count += 1
            if self.termination_call_count >= 2:
                return ProcessingResult.REMOVED
            return None

        async def status_side_effect(_ctx, _sm, _pipeline, _retried_jobs):
            self.status_call_count += 1
            return None  # Continue polling

        self.mock_sleep = AsyncMock(return_value=True)
        self.termination_side_effect = termination_side_effect
        self.status_side_effect = status_side_effect
        self.no_result_rebase = no_result_rebase

    async def when_wait_for_pipeline_is_called(self):
        handler = self.processor._pipeline_handler
        with (
            patch.object(
                handler,
                "check_pipeline_termination_conditions",
                new_callable=AsyncMock,
                side_effect=self.termination_side_effect,
            ),
            patch(
                "gitlab_queue.core.pipeline_handler.maybe_rebase_during_testing",
                new_callable=AsyncMock,
                return_value=self.no_result_rebase,
            ),
            patch.object(
                handler,
                "should_skip_stale_pipeline",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                handler,
                "handle_pipeline_status",
                new_callable=AsyncMock,
                side_effect=self.status_side_effect,
            ),
            patch.object(
                handler,
                "_interruptible_sleep",
                self.mock_sleep,
            ),
        ):
            self.result = await self.processor._wait_for_pipeline(self.ctx)

    def then_result_is_removed(self):
        assert self.result == ProcessingResult.REMOVED

    def and_handle_pipeline_status_returned_none(self):
        assert self.status_call_count >= 1

    def and_sleep_was_called(self):
        self.mock_sleep.assert_called()
