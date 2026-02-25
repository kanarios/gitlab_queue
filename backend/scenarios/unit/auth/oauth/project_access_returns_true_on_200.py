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
        """
        Calls validate_project_access with httpx.AsyncClient patched to return the prepared mock client and saves the call result.
        
        Patches gitlab_queue.auth.oauth.httpx.AsyncClient to return self.mock_client, invokes validate_project_access with gitlab_url "https://gitlab.example.com", access_token "test-token", and project_id 123, and stores the returned value in self.result.
        """
        with patch("gitlab_queue.auth.oauth.httpx.AsyncClient", return_value=self.mock_client):
            self.result = await validate_project_access(
                gitlab_url="https://gitlab.example.com",
                access_token="test-token",
                project_id=123,
            )

    def then_it_should_return_true(self):
        """
        Assert that the validation result is True.
        
        Raises:
            AssertionError: If self.result is not True.
        """
        assert self.result is True

    def and_it_should_call_correct_url(self):
        """
        Asserts the mocked HTTP client's GET was awaited once and that it was called with the expected GitLab project URL and Authorization header.
        
        Checks:
        - the GET coroutine was awaited exactly one time.
        - the requested URL equals "https://gitlab.example.com/api/v4/projects/123".
        - the "Authorization" header equals "Bearer test-token".
        """
        self.mock_client.get.assert_awaited_once()
        call_args = self.mock_client.get.call_args
        assert call_args[0][0] == "https://gitlab.example.com/api/v4/projects/123"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
