"""Test scenario: check_rebase_status sees a running rebase.

Right after PUT /rebase GitLab keeps rebasing in the background.
check_rebase_status must fetch the MR with include_rebase_in_progress=true,
otherwise GitLab omits the field and the rebase is reported as finished
before it has even started.
"""

from __future__ import annotations

import vedro

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import rebasing_mr_handler


class Scenario(vedro.Scenario):
    subject = "check_rebase_status requests rebase_in_progress from GitLab"

    def given_mock_gitlab_with_rebase_running(self):
        self.transport = GitLabMockTransport()
        self.transport.register_handler(
            "GET",
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            rebasing_mr_handler(iid=42),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_check_rebase_status_is_called(self):
        self.in_progress, self.has_conflicts, _ = await self.client.check_rebase_status(42)

    def then_include_rebase_in_progress_is_sent(self):
        assert self.transport.history[-1].url.params.get("include_rebase_in_progress") == "true"

    def and_rebase_is_reported_in_progress(self):
        assert self.in_progress is True
        assert self.has_conflicts is False

    async def do_cleanup(self):
        await self.client.close()
