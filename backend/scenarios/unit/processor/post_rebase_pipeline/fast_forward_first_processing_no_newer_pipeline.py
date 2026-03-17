"""Test wait_for_post_rebase_pipeline accepts current pipeline in first-processing (no newer exists).

When SHA is unchanged (fast-forward), pipeline.id == old_pipeline_id (running),
and NO newer pipeline exists in get_mr_pipelines,
the handler should return the current pipeline as-is.

This is a regression test ensuring first-processing still works correctly.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import instant_poll

OLD_PIPELINE_ID = 1000


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline accepts current pipeline in first-processing"

    def given_mr_with_running_pipeline_and_no_newer(self):
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
            poll_fn=instant_poll,
        )

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.result_pipeline, self.new_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=OLD_PIPELINE_ID,
        )

    def then_current_pipeline_is_returned(self):
        assert self.result_pipeline is not None
        assert self.result_pipeline.id == OLD_PIPELINE_ID

    def then_sha_matches(self):
        assert self.new_sha == self.sha

    def then_create_pipeline_was_not_called(self):
        assert self.gitlab_client.create_pipeline_calls == []
