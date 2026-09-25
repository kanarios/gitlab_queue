"""Transport errors update the latest GitLab request outcome."""

from __future__ import annotations

import httpx
import vedro
from vedro import catched

from scenarios.contexts.gitlab_client_factory import created_test_client


def _raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection failed", request=request)


class Scenario(vedro.Scenario):
    subject = "GitLab request errors mark last request as failed"

    def given_transport_that_cannot_connect(self):
        self.client = created_test_client(transport=httpx.MockTransport(_raise_connect_error))

    async def when_request_fails(self):
        with catched(httpx.RequestError) as self.request_error:
            await self.client.get("/merge_requests/42")

    def then_transport_error_is_raised(self):
        assert self.request_error.type is httpx.ConnectError

    def and_last_request_is_marked_as_failed(self):
        assert self.client.last_request_succeeded is False

    async def do_cleanup(self):
        await self.client.close()
