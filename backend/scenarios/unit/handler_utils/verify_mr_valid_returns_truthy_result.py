"""Test verify_mr_in_queue returns truthy VerifyResult for valid MR."""

from __future__ import annotations

import vedro

from gitlab_queue.core.handler_utils import verify_mr_in_queue
from scenarios.fakes import FakeGitLabClient, FakeSettings, create_mr


class Scenario(vedro.Scenario):
    subject = "verify_mr_in_queue returns truthy result for valid MR"

    def given_opened_mr_with_queue_label(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={
                42: create_mr(iid=42, state="opened", labels=["merge_queue"]),
            },
        )
        self.settings = FakeSettings()

    async def when_verify_mr_in_queue_is_called(self):
        self.result = await verify_mr_in_queue(self.gitlab_client, self.settings, 42)

    def then_result_is_truthy(self):
        assert self.result

    def and_valid_attribute_is_true(self):
        assert self.result.valid is True
