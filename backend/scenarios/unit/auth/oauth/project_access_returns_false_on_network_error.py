"""Test that validate_project_access returns False on network error."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns False on network error"

    def given_gitlab_network_error(self):
        """
        Prepare self.mock_client as an AsyncMock that simulates a GitLab network failure.

        Sets self.mock_client.get to raise an httpx.ConnectError("Connection refused") when awaited and configures __aenter__ and __aexit__ so the mock can be used in an async with context.
        """
        self.mock_client = AsyncMock()
        self.mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    async def when_project_access_is_validated(self):
        """
        Patch httpx.AsyncClient to use the prepared mock client and invoke validate_project_access, storing the call result on self.result.

        This step replaces gitlab_queue.auth.oauth.httpx.AsyncClient with a factory that returns self.mock_client, then awaits validate_project_access with a sample GitLab URL, access token, and project ID and saves the returned value to self.result.
        """
        with patch("gitlab_queue.auth.oauth.httpx.AsyncClient", return_value=self.mock_client):
            self.result = await validate_project_access(
                gitlab_url="https://gitlab.example.com",
                access_token="test-token",
                project_id=123,
            )

    def then_it_should_return_false(self):
        assert self.result is False
