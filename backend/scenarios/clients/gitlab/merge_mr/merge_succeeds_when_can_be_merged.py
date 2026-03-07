"""Test merge_mr succeeds when merge_status is 'can_be_merged'."""

import vedro

from scenarios.transports import GitLabMockTransport
from scenarios.transports.responses import mr_response

from ._helpers import (
    PROJECT_ID,
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
    mr_merge_path,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr succeeds when merge_status is 'can_be_merged'"

    def given_mr_ready_to_merge(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [mr_get_response(self.iid, merge_status="can_be_merged")],
        )
        self.transport.register_put(
            mr_merge_path(self.iid),
            json_data=mr_response(iid=self.iid, project_id=PROJECT_ID, state="merged"),
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        self.result = await self.client.merge_mr(self.iid)

    def then_mr_is_merged(self):
        assert self.result.state == "merged"

    def and_get_mr_called_once(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == 1

    def and_put_called_with_merge_endpoint(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 1
        assert f"/merge_requests/{self.iid}/merge" in put_requests[0].url.path
