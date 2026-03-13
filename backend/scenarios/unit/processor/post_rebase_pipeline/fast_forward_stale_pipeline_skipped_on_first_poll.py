"""Test wait_for_post_rebase_pipeline skips stale pipeline on first poll in fast-forward case.

When SHA is unchanged (fast-forward) and the pipeline ID matches old_pipeline_id,
the first poll should skip it as possibly stale (grace period).
With instant_poll (single call), this results in timeout → pipeline returned from timeout handler.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import instant_poll


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline skips stale pipeline on first poll in fast-forward"

    def given_mr_with_unchanged_sha_and_matching_pipeline(self):
        self.sha = "abc123"
        self.old_pipeline_id = 555
        self.pipeline = create_pipeline(id=self.old_pipeline_id, sha=self.sha, status="success")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=self.pipeline,
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
        self.returned_pipeline, self.returned_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=self.old_pipeline_id,
        )

    def then_pipeline_is_returned_from_timeout_handler(self):
        assert self.returned_pipeline is not None

    def then_pipeline_id_matches(self):
        assert self.returned_pipeline.id == self.old_pipeline_id

    def then_sha_matches(self):
        assert self.returned_sha == self.sha
