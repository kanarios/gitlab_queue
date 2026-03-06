"""Test that validate_project_access returns False on network error."""

from __future__ import annotations

import httpx
import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns False on network error"

    def given_gitlab_network_error(self):
        def raise_connect_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        self.transport = httpx.MockTransport(raise_connect_error)

    async def when_project_access_is_validated(self):
        self.result = await validate_project_access(
            gitlab_url="https://gitlab.example.com",
            access_token="test-token",
            project_id=123,
            transport=self.transport,
        )

    def then_it_should_return_false(self):
        assert self.result is False
