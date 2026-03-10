"""Test merge_mr returns success when MR is already merged externally."""

import vedro

from scenarios.transports import GitLabMockTransport

from ._helpers import (
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr returns success when MR is already merged externally"

    def given_mr_already_merged(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [mr_get_response(self.iid, state="merged")],
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(self.iid)

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_no_put_requests_made(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 0

    def and_get_called_once(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == 1
