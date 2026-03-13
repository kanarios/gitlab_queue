"""Test _process_pipeline_iteration resets wait state on pipeline switch.

When check_stale_pipeline returns SWITCHED, the caller must:
1. Update pipeline_id in the database
2. Reset start_time, retried_jobs, and canceled_seen_count in PipelineWaitState
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from gitlab_queue.core.types import RebaseCheckOutcome
from scenarios.fakes import FakeGitLabClient, FakeQueueManager

from .._helpers import (
    create_mock_pipeline,
    create_pipeline_wait_state,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)


async def _no_rebase_needed(settings, ctx, state, pipeline):
    return RebaseCheckOutcome(
        context=None,
        result=None,
        last_check=datetime.now(UTC),
        should_reset=False,
    )


class Scenario(vedro.Scenario):
    subject = "process pipeline iteration resets wait state when pipeline is switched"

    def given_queue_item_tracking_old_pipeline(self):
        self.queue_manager = FakeQueueManager()
        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=100,
            expected_sha="abc12345",
        )
        self.queue_manager.add_item(self.queue_item)

    def given_gitlab_returns_newer_pipeline_with_matching_sha(self):
        self.newer_pipeline = create_mock_pipeline(
            pipeline_id=200,
            sha="abc12345",
            status="running",
        )
        self.gitlab_client = FakeGitLabClient(
            latest_pipeline_response=self.newer_pipeline,
        )

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            rebase_check_fn=_no_rebase_needed,
        )

    def given_wait_state_with_stale_data(self):
        self.old_start_time = datetime.now(UTC) - timedelta(seconds=10)
        self.state = create_pipeline_wait_state(
            start_time=self.old_start_time,
            retried_jobs={"build": 2, "test": 1},
        )
        self.state.canceled_seen_count = 3

    def given_processing_context(self):
        self.ctx = create_processing_context(mr_iid=42)

    async def when_process_pipeline_iteration_is_called(self):
        self.result = await self.handler._process_pipeline_iteration(
            self.ctx,
            self.state,
            timeout=timedelta(hours=1),
        )

    def then_result_is_none(self):
        assert self.result is None

    def then_start_time_is_reset(self):
        assert self.state.start_time > self.old_start_time

    def then_retried_jobs_are_cleared(self):
        assert self.state.retried_jobs == {}

    def then_canceled_seen_count_is_reset(self):
        assert self.state.canceled_seen_count == 0

    def then_pipeline_id_is_updated_in_database(self):
        calls = self.queue_manager.update_state_calls
        assert len(calls) == 1
        assert calls[0]["mr_iid"] == 42
        assert calls[0]["pipeline_id"] == 200

    def then_state_is_testing(self):
        calls = self.queue_manager.update_state_calls
        assert calls[0]["state"] == "testing"

    def then_retried_jobs_are_cleared_in_database(self):
        calls = self.queue_manager.update_state_calls
        assert calls[0]["retried_jobs"] == {}
