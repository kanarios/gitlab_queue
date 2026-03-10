"""Test merge_mr succeeds after 405 when MR was merged externally."""

import vedro

from scenarios.transports import GitLabMockTransport

from ._helpers import (
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
    mr_merge_path,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr succeeds after 405 when MR was merged externally"

    def given_mr_returns_405_then_already_merged(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [
                mr_get_response(self.iid, merge_status="can_be_merged", state="opened"),
                mr_get_response(self.iid, state="merged"),
            ],
        )
        self.transport.register_put(
            mr_merge_path(self.iid),
            status=405,
            json_data={"message": "Method Not Allowed"},
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(self.iid)

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_called_twice(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == 2

    def and_put_called_once(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 1
