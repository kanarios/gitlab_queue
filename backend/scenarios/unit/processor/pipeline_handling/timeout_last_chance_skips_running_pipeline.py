"""Test timeout last-chance does NOT rescue a running pipeline.

When timeout is reached and pipeline is still running (not terminal),
the handler should trigger a real TIMEOUT — last-chance only applies
to terminal statuses (failed, canceled, canceling).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
    create_test_pipeline_handler,
)


class Scenario(vedro.Scenario):
    subject = "timeout last chance does not rescue running pipeline"

    def given_gitlab_client_with_running_pipeline(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.latest_pipeline_response = create_mock_pipeline(
            pipeline_id=100,
            sha="abc123",
            status="running",
        )

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(gitlab_client=self.gitlab_client)

    def given_processing_context(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    def given_expired_timeout(self):
        self.timeout = timedelta(seconds=7200)
        self.start_time = datetime.now(UTC) - timedelta(seconds=7201)

    def given_pipeline_wait_state(self):
        self.state = create_pipeline_wait_state(start_time=self.start_time)

    async def when_check_termination_is_called(self):
        self.result = await self.handler.check_pipeline_termination_conditions(
            ctx=self.ctx,
            sm=self.sm,
            timeout=self.timeout,
            start_time=self.start_time,
            state=self.state,
        )

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT

    def and_timeout_was_triggered(self):
        assert len(self.sm.timeout_calls) == 1

    def and_last_chance_flag_is_not_set(self):
        assert self.state.timeout_last_chance_used is False
