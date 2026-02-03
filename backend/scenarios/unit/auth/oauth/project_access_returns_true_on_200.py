"""Test that validate_project_access returns True when GitLab returns 200."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns True on 200"

    def given_gitlab_returns_200(self):
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_client = AsyncMock()
        self.mock_client.get = AsyncMock(return_value=self.mock_response)
        self.mock_client.__aenter__ = AsyncMock(return_value=self.mock_client)
        self.mock_client.__aexit__ = AsyncMock(return_value=None)

    async def when_project_access_is_validated(self):
        with patch("gitlab_queue.auth.oauth.httpx.AsyncClient", return_value=self.mock_client):
            self.result = await validate_project_access(
                gitlab_url="https://gitlab.example.com",
                access_token="test-token",
                project_id=123,
            )

    def then_it_should_return_true(self):
        assert self.result is True

    def and_it_should_call_correct_url(self):
        self.mock_client.get.assert_called_once()
        call_args = self.mock_client.get.call_args
        assert call_args[0][0] == "https://gitlab.example.com/api/v4/projects/123"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
