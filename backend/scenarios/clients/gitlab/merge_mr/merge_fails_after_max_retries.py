"""Test merge_mr fails after max retries when status stays 'checking'."""

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
    subject = "merge_mr fails after max retries when status stays 'checking'"

    def given_mr_always_checking(self):
        self.iid = 42
        self.max_retries = 10
        self.transport = GitLabMockTransport()
        self.transport.register_sequence(
            "GET",
            mr_get_path(self.iid),
            [mr_get_response(self.iid, merge_status="checking")] * self.max_retries,
        )
        self.client = create_merge_mr_client(
            self.transport,
            merge_status_retry_max=self.max_retries,
        )

    async def when_merge_mr_is_called(self):
        with catched(GitLabConflictError) as self.exception:
            await self.client.merge_mr(self.iid)

    def then_conflict_error_is_raised(self):
        assert self.exception.type is GitLabConflictError

    def and_error_message_contains_timeout(self):
        assert "timeout" in str(self.exception.value).lower()

    def and_get_mr_called_ten_times(self):
        get_requests = [r for r in self.transport.history if r.method == "GET"]
        assert len(get_requests) == self.max_retries

    def and_put_never_called(self):
        put_requests = [r for r in self.transport.history if r.method == "PUT"]
        assert len(put_requests) == 0
