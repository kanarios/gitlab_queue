"""Test merge_mr retries on HTTP 422 when has_conflicts=False, then succeeds."""

import vedro

from scenarios.transports import GitLabMockTransport

from ._helpers import (
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
    mr_merge_error_response,
    mr_merge_path,
    mr_merge_response,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr retries on HTTP 422 when has_conflicts=False, then succeeds"

    def given_mr_ready_but_api_returns_422_initially(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [
                mr_get_response(self.iid, merge_status="can_be_merged", has_conflicts=False),
                mr_get_response(self.iid, merge_status="can_be_merged", has_conflicts=False),
            ],
        )
        self.transport.register_sequence(
            "PUT",
            mr_merge_path(self.iid),
            [
                mr_merge_error_response(status=422, message="Branch cannot be merged"),
                mr_merge_response(self.iid, state="merged"),
            ],
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(self.iid)

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_mr_called_twice(self):
        get_requests = self.transport.get_requests("GET", mr_get_path(self.iid))
        assert len(get_requests) == 2

    def and_put_merge_called_twice(self):
        merge_path = f"/api/v4/projects/123/merge_requests/{self.iid}/merge"
        put_requests = self.transport.get_requests("PUT", merge_path)
        assert len(put_requests) == 2
