"""Test scenario: get_mr always requests rebase_in_progress.

GitLab returns rebase_in_progress only for requests carrying
include_rebase_in_progress=true. Without it the field defaults to False and
a running rebase looks finished, so get_mr sends it on every call, alongside
the opt-in include_diverged_commits_count.
"""

from __future__ import annotations

import vedro
from vedro import params

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import rebasing_mr_handler


class Scenario(vedro.Scenario):
    subject = "get_mr requests rebase_in_progress (include_diverged_commits_count={diverged})"

    @params(False)
    @params(True)
    def __init__(self, diverged: bool):
        self.diverged = diverged

    def given_mock_gitlab_with_rebase_running(self):
        self.transport = GitLabMockTransport()
        self.transport.register_handler(
            "GET",
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            rebasing_mr_handler(iid=42),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(42, include_diverged_commits_count=self.diverged)

    def then_include_rebase_in_progress_is_sent(self):
        assert self.transport.history[-1].url.params.get("include_rebase_in_progress") == "true"

    def and_rebase_in_progress_is_parsed(self):
        assert self.result.rebase_in_progress is True

    async def do_cleanup(self):
        await self.client.close()
