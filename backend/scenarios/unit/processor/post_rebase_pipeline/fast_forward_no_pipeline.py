"""Test wait_for_post_rebase_pipeline creates pipeline when fast-forward and no pipeline found.

When SHA is unchanged (fast-forward) and no pipeline exists, GitLab won't create one
automatically, so the bot creates it via create_pipeline().
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.core.rebase_handler import RebaseHandler
from scenarios.fakes import FakeGitLabClient, FakeNotifier, FakeSettings, create_mr, create_pipeline

from .._helpers import instant_poll


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline creates pipeline when fast-forward and no pipeline found"

    def given_mr_with_no_pipeline(self):
        self.sha = "abc123"
        self.new_pipeline = create_pipeline(id=7777, sha=self.sha, status="running")
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha=self.sha, source_branch="my-feature")},
            latest_pipeline_response=None,
            created_pipeline=self.new_pipeline,
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
            old_pipeline_id=None,
        )

    def then_create_pipeline_was_called(self):
        assert self.gitlab_client.create_pipeline_calls == ["my-feature"]

    def then_new_pipeline_is_returned(self):
        assert self.pipeline is not None

    def then_returned_pipeline_id_matches(self):
        assert self.pipeline.id == self.new_pipeline.id

    def then_sha_matches(self):
        assert self.new_sha == self.sha
