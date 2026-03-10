"""Test: create_pipeline and retry_pipeline both fail → error propagates.

When create_pipeline returns 400 and retry_pipeline also fails,
the error from retry_pipeline should propagate.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "create_pipeline and retry_pipeline both fail propagates error"

    def given_mr_with_failed_pipeline(self):
        self.sha = "abc123"
        self.old_pipeline_id = 100
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=create_pipeline(id=self.old_pipeline_id, sha=self.sha, status="failed"),
            create_pipeline_error=GitLabAPIError("No stages/jobs for this pipeline", status_code=400),
            retry_pipeline_error=GitLabAPIError("Retry failed", status_code=400),
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
        try:
            await self.handler.wait_for_post_rebase_pipeline(
                mr_iid=42,
                old_sha=self.sha,
                old_pipeline_id=self.old_pipeline_id,
            )
            self.error = None
        except GitLabAPIError as e:
            self.error = e

    def then_error_is_raised(self):
        assert self.error is not None

    def then_retry_pipeline_was_attempted(self):
        assert self.gitlab_client.retry_pipeline_calls == [self.old_pipeline_id]
