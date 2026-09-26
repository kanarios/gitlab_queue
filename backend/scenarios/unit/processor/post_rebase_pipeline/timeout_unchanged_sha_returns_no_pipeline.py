"""Test wait_for_post_rebase_pipeline reports an unchanged SHA at timeout.

While the SHA is unchanged after a rebase, GitLab may simply not have updated
it yet, so no pipeline is looked up or created. If it never changes, the
caller gets (None, old_sha) and decides the rebase was a no-op.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_test_rebase_handler, exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "timeout with unchanged SHA returns no pipeline and creates none"

    def given_mr_whose_sha_never_changes(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123")},
            latest_pipeline_response=create_pipeline(id=100, sha="abc123", status="failed"),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client, poll_fn=exhaustive_poll)

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.sha = await self.handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha="abc123",
            old_pipeline_id=100,
        )

    def then_no_pipeline_is_returned(self):
        assert self.pipeline is None
        assert self.sha == "abc123"

    def and_pipelines_were_not_listed(self):
        assert self.gitlab_client.get_latest_pipeline_calls == []

    def and_no_pipeline_was_created(self):
        assert self.gitlab_client.create_pipeline_calls == []
