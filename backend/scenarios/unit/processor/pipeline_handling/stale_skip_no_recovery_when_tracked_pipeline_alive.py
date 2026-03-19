"""Test pipeline handler does not recover from stale skip when tracked pipeline is still running.

When check_stale_pipeline returns SKIP and the tracked pipeline is still alive
(running/pending), the handler should NOT switch — just skip and wait.

Regression test: ensures recovery only triggers for dead tracked pipelines.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import vedro

from scenarios.fakes import FakeGitLabClient, FakeQueueManager, FakeSettings, create_pipeline

from .._helpers import (
    create_mock_state_machine,
    create_pipeline_wait_state,
    create_processing_context,
    create_test_pipeline_handler,
    create_test_queue_item,
)

TRACKED_PIPELINE_ID = 1000
NEWER_PIPELINE_ID = 2000


class Scenario(vedro.Scenario):
    subject = "pipeline handler does not recover from stale skip when tracked pipeline is still running"

    def given_queue_item_with_tracked_pipeline(self):
        self.queue_manager = FakeQueueManager()
        self.queue_item = create_test_queue_item(
            mr_iid=42,
            state="testing",
            pipeline_id=TRACKED_PIPELINE_ID,
            expected_sha="sha_old",
        )
        self.queue_manager.add_item(self.queue_item)

    def given_gitlab_client_with_newer_pipeline_and_alive_tracked(self):
        self.gitlab_client = FakeGitLabClient(
            latest_pipeline_response=create_pipeline(id=NEWER_PIPELINE_ID, sha="sha_new", status="running"),
            pipeline_responses={
                TRACKED_PIPELINE_ID: create_pipeline(id=TRACKED_PIPELINE_ID, sha="sha_old", status="running"),
            },
        )

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
            settings=FakeSettings(),
            shutdown_event=asyncio.Event(),
        )

    def given_processing_context_and_state(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        self.state = create_pipeline_wait_state()
        self.timeout = timedelta(hours=2)

    async def when_process_pipeline_iteration_is_called(self):
        self.result = await self.handler._process_pipeline_iteration(
            self.ctx,
            self.state,
            self.timeout,
        )

    def then_result_is_none(self):
        assert self.result is None

    def then_no_pipeline_switch_occurred(self):
        pipeline_updates = [c for c in self.queue_manager.update_state_calls if "pipeline_id" in c]
        assert pipeline_updates == []

    def then_pipeline_failed_was_not_called(self):
        assert self.sm.pipeline_failed_calls == []
