"""Test wait_for_post_rebase_pipeline prefers newer pipeline in fast-forward re-processing.

When SHA is unchanged (fast-forward), pipeline.id == old_pipeline_id (running),
and a newer pipeline with matching SHA exists in get_mr_pipelines,
the handler should return the newer pipeline instead of the old one.

This prevents the re-processing case from binding to an old/retried pipeline.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import instant_poll

OLD_PIPELINE_ID = 1000
NEWER_PIPELINE_ID = 2000


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline prefers newer pipeline in fast-forward re-processing"

    def given_mr_with_running_old_pipeline_and_newer_available(self):
        self.sha = "abc123"
        self.old_pipeline = create_pipeline(id=OLD_PIPELINE_ID, sha=self.sha, status="running")
        self.newer_pipeline = create_pipeline(id=NEWER_PIPELINE_ID, sha=self.sha, status="running")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=self.old_pipeline,
            mr_pipelines_response=[
                self.old_pipeline,
                self.newer_pipeline,
            ],
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
            old_pipeline_id=OLD_PIPELINE_ID,
        )

    def then_newer_pipeline_is_returned(self):
        assert self.pipeline is not None
        assert self.pipeline.id == NEWER_PIPELINE_ID

    def then_sha_matches(self):
        assert self.new_sha == self.sha

    def then_create_pipeline_was_not_called(self):
        assert self.gitlab_client.create_pipeline_calls == []
