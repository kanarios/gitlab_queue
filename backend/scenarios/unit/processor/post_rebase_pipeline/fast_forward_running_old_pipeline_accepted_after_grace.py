"""Test wait_for_post_rebase_pipeline accepts running old pipeline after grace when no newer exists.

When SHA is unchanged (fast-forward), pipeline.id == old_pipeline_id (running),
and no newer pipeline ever appears, the handler should accept the old pipeline
after the grace period (STALE_PIPELINE_GRACE_POLLS iterations).

This prevents indefinite waiting when there truly is no newer pipeline.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import STALE_PIPELINE_GRACE_POLLS, RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import exhaustive_poll

OLD_PIPELINE_ID = 1000


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline accepts running old pipeline after grace when no newer exists"

    def given_mr_with_running_old_pipeline_and_no_newer(self):
        self.sha = "abc123"
        self.pipeline = create_pipeline(id=OLD_PIPELINE_ID, sha=self.sha, status="running")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=self.pipeline,
            mr_pipelines_response=[self.pipeline],
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
        self.result_pipeline, self.new_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=OLD_PIPELINE_ID,
        )

    def then_old_pipeline_is_returned(self):
        assert self.result_pipeline is not None
        assert self.result_pipeline.id == OLD_PIPELINE_ID

    def then_sha_matches(self):
        assert self.new_sha == self.sha

    def then_grace_period_was_respected(self):
        # STALE_PIPELINE_GRACE_POLLS=2: first call skip_count=1 (1<2 -> CONTINUE),
        # second call skip_count=2 (2<2 is False -> accept).
        # Each iteration calls get_mr + get_latest_mr_pipeline + get_mr_pipelines.
        assert len(self.gitlab_client.get_mr_calls) == STALE_PIPELINE_GRACE_POLLS
