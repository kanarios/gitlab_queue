"""Test wait_for_post_rebase_pipeline waits for newer pipeline when old is running in fast-forward.

When SHA is unchanged (fast-forward), pipeline.id == old_pipeline_id (running),
and no newer pipeline exists YET, the handler should NOT accept the old pipeline
immediately. Instead it waits (grace period), and when a newer pipeline appears,
returns the newer one.

This is the core fix for the race condition where the bot binds the OLD pipeline
after rebase instead of waiting for the NEW one created by GitLab ~6 seconds later.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import exhaustive_poll

OLD_PIPELINE_ID = 1000
NEW_PIPELINE_ID = 2000


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline waits for newer pipeline when old is running in fast-forward"

    def given_mr_with_running_old_pipeline(self):
        self.sha = "abc123"
        self.old_pipeline = create_pipeline(id=OLD_PIPELINE_ID, sha=self.sha, status="running")
        self.new_pipeline = create_pipeline(id=NEW_PIPELINE_ID, sha=self.sha, status="running")

    def given_gitlab_client_with_delayed_newer_pipeline(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=self.old_pipeline,
            # First call: only old pipeline; second call: old + new pipeline
            mr_pipelines_response_sequence=[
                [self.old_pipeline],
                [self.old_pipeline, self.new_pipeline],
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
        self.result_pipeline, self.new_sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.sha,
            old_pipeline_id=OLD_PIPELINE_ID,
        )

    def then_newer_pipeline_is_returned(self):
        assert self.result_pipeline is not None
        assert self.result_pipeline.id == NEW_PIPELINE_ID

    def then_old_pipeline_is_not_returned(self):
        assert self.result_pipeline.id != OLD_PIPELINE_ID

    def then_sha_matches(self):
        assert self.new_sha == self.sha
