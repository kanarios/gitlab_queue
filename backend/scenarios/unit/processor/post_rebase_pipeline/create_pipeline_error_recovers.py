"""Test: create_pipeline server error recovers on next poll with auto-created pipeline.

In fast-forward case, if create_pipeline fails with a server error (5xx),
the polling should CONTINUE and succeed on the next iteration when a pipeline appears.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "create_pipeline server error recovers on next poll with auto-created pipeline"

    def given_mr_with_failed_then_running_pipeline(self):
        self.sha = "abc123"
        self.running_pipeline = create_pipeline(id=200, sha=self.sha, status="running")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_sequence=[
                create_pipeline(id=100, sha=self.sha, status="failed"),
                self.running_pipeline,
            ],
            create_pipeline_error_sequence=[
                GitLabServerError("Internal Server Error", status_code=500),
            ],
        )

    def given_rebase_handler(self):
        self.handler = RebaseHandler(
            gitlab_client=self.gitlab_client,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            shutdown_event=asyncio.Event(),
            poll_fn=exhaustive_poll,
        )

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=None,
        )

    def then_pipeline_is_returned(self):
        assert self.pipeline is not None

    def then_returned_pipeline_is_running(self):
        assert self.pipeline.id == self.running_pipeline.id

    def then_sha_matches(self):
        assert self.new_sha == self.sha
