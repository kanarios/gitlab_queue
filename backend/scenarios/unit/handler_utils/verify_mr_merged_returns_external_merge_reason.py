"""Test verify_mr_in_queue returns external_merge reason for merged MR."""

from __future__ import annotations

import vedro

from gitlab_queue.core.handler_utils import verify_mr_in_queue
from scenarios.fakes import FakeGitLabClient, FakeSettings, create_mr


class Scenario(vedro.Scenario):
    subject = "verify_mr_in_queue returns external_merge reason for merged MR"

    def given_merged_mr_with_queue_label(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={
                42: create_mr(iid=42, state="merged", labels=["merge_queue"]),
            },
        )
        self.settings = FakeSettings()

    async def when_verify_mr_in_queue_is_called(self):
        self.result = await verify_mr_in_queue(self.gitlab_client, self.settings, 42)

    def then_result_is_falsy(self):
        assert not self.result

    def then_reason_is_external_merge(self):
        assert self.result.reason == "external_merge"

    def and_queue_label_was_removed_via_api(self):
        assert (42, "merge_queue") in self.gitlab_client.remove_label_calls
