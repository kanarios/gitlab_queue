"""Test that validate_project_access returns True when GitLab returns 200."""

from __future__ import annotations

import httpx
import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns True on 200"

    def given_gitlab_returns_200(self):
        self.transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"id": 123}))

    async def when_project_access_is_validated(self):
        self.result = await validate_project_access(
            gitlab_url="https://gitlab.example.com",
            access_token="test-token",
            project_id=123,
            transport=self.transport,
        )

    def then_it_should_return_true(self):
        assert self.result is True
