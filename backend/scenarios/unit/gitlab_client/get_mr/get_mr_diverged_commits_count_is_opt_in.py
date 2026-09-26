"""Test scenario: get_mr requests diverged_commits_count only when asked.

GitLab returns diverged_commits_count only for requests carrying
include_diverged_commits_count=true. Computing it costs GitLab extra Gitaly
work and get_mr is polled frequently, so the parameter is opt-in; without it
the field is unknown (None).
"""

from __future__ import annotations

import vedro
from vedro import params

from scenarios.contexts.gitlab_client_factory import TEST_PROJECT_ID, created_test_client
from scenarios.transports import GitLabMockTransport

from ._helpers import create_mr_api_response


class Scenario(vedro.Scenario):
    subject = "get_mr with include_diverged_commits_count={requested}"

    @params(True, "true", 3)
    @params(False, None, None)
    def __init__(self, requested: bool, expected_param: str | None, expected_count: int | None):
        self.requested = requested
        self.expected_param = expected_param
        self.expected_count = expected_count

    def given_mock_gitlab_returning_diverged_count_when_asked(self):
        self.transport = GitLabMockTransport()
        self.transport.register_get(
            f"/api/v4/projects/{TEST_PROJECT_ID}/merge_requests/42",
            json_data=create_mr_api_response(iid=42, diverged_commits_count=self.expected_count),
        )
        self.client = created_test_client(transport=self.transport)

    async def when_get_mr_is_called(self):
        self.result = await self.client.get_mr(42, include_diverged_commits_count=self.requested)

    def then_query_param_matches_request(self):
        assert self.transport.history[-1].url.params.get("include_diverged_commits_count") == self.expected_param

    def and_diverged_commits_count_is_parsed(self):
        assert self.result.diverged_commits_count == self.expected_count

    async def do_cleanup(self):
        await self.client.close()
