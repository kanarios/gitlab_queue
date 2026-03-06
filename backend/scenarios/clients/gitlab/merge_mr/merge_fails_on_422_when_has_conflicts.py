"""Test merge_mr fails immediately on HTTP 422 when has_conflicts=True."""

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.transports import GitLabMockTransport

from ._helpers import (
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
    mr_merge_error_response,
    mr_merge_path,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr fails immediately on HTTP 422 when has_conflicts=True"

    def given_mr_with_conflicts_and_api_returns_422(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [mr_get_response(self.iid, merge_status="can_be_merged", has_conflicts=True)],
        )
        error_resp = mr_merge_error_response(status=422)
        self.transport.register_sequence(
            "PUT",
            mr_merge_path(self.iid),
            [error_resp],
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        with catched(GitLabAPIError) as self.exception:
            await self.client.merge_mr(self.iid)

    def then_api_error_is_raised(self):
        assert self.exception.type is GitLabAPIError

    def and_error_has_status_422(self):
        assert self.exception.value.status_code == 422

    def and_get_mr_called_once(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == 1

    def and_put_called_once(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 1
