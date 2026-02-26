"""Test that validate_project_access returns False when GitLab returns 404."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import vedro

from gitlab_queue.auth.oauth import validate_project_access


class Scenario(vedro.Scenario):
    subject = "validate_project_access returns False on 404"

    def given_gitlab_returns_404(self):
        """
        Prepare test attributes that simulate a GitLab HTTP 404 response.

        Creates:
        - self.mock_response: a MagicMock with status_code set to 404.
        - self.mock_client: an AsyncMock whose .get() returns self.mock_response and which implements async context manager methods (__aenter__/__aexit__).
        """
        self.mock_response = MagicMock()
        self.mock_response.status_code = 404
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

    def then_it_should_return_false(self):
        assert self.result is False
