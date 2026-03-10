"""Test: create_pipeline client error falls back to retry_pipeline.

In fast-forward case, if create_pipeline fails with 400 (e.g. workflow:rules
blocks source=api), the handler should fall back to retry_pipeline using
the old_pipeline_id.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import instant_poll


class Scenario(vedro.Scenario):
    subject = "create_pipeline client error falls back to retry_pipeline"

    def given_mr_with_failed_pipeline(self):
        self.sha = "abc123"
        self.old_pipeline_id = 100
        self.retried_pipeline = create_pipeline(id=200, sha=self.sha, status="pending")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=create_pipeline(id=self.old_pipeline_id, sha=self.sha, status="failed"),
            create_pipeline_error=GitLabAPIError("No stages/jobs for this pipeline", status_code=400),
            retry_pipeline_response=self.retried_pipeline,
        )

    def given_rebase_handler(self):
        self.handler = RebaseHandler(
            gitlab_client=self.gitlab_client,
            notifier=FakeNotifier(),
            settings=FakeSettings(),
            shutdown_event=asyncio.Event(),
            poll_fn=instant_poll,
        )

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=self.old_pipeline_id,
        )

    def then_create_pipeline_was_attempted(self):
        assert self.gitlab_client.create_pipeline_calls == ["my-feature"]

    def then_retry_pipeline_was_called_with_old_pipeline_id(self):
        assert self.gitlab_client.retry_pipeline_calls == [self.old_pipeline_id]

    def then_retried_pipeline_is_returned(self):
        assert self.pipeline is not None
        assert self.pipeline.id == self.retried_pipeline.id

    def then_sha_matches(self):
        assert self.new_sha == self.sha
