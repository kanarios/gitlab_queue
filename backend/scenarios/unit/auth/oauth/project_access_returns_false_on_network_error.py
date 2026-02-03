"""Test that validate_project_access returns False on network error."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns False on network error"

    def given_gitlab_network_error(self):
        self.mock_client = AsyncMock()
        self.mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    async def when_project_access_is_validated(self):
        with patch("gitlab_queue.auth.oauth.httpx.AsyncClient", return_value=self.mock_client):
            self.result = await validate_project_access(
                gitlab_url="https://gitlab.example.com",
                access_token="test-token",
                project_id=123,
            )

    def then_it_should_return_false(self):
        assert self.result is False
