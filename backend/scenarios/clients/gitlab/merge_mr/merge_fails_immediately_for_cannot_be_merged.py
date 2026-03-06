"""Test merge_mr fails immediately when merge_status is 'cannot_be_merged'."""

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabConflictError
from scenarios.transports import GitLabMockTransport

from ._helpers import (
    create_merge_mr_client,
    mr_get_path,
    mr_get_response,
)


class Scenario(vedro.Scenario):
    subject = "merge_mr fails immediately when merge_status is 'cannot_be_merged'"

    def given_mr_cannot_be_merged(self):
        self.iid = 42
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [mr_get_response(self.iid, merge_status="cannot_be_merged", has_conflicts=True)],
        )
        self.client = create_merge_mr_client(self.transport)

    async def when_merge_mr_is_called(self):
        with catched(GitLabConflictError) as self.exception:
            await self.client.merge_mr(self.iid)

    def then_conflict_error_is_raised(self):
        assert self.exception.type is GitLabConflictError

    def and_error_message_contains_status(self):
        assert "cannot_be_merged" in str(self.exception.value)

    def and_get_mr_called_once(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == 1

    def and_put_never_called(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 0
