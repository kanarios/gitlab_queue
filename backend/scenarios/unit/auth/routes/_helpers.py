"""Helper functions for auth route tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def create_mock_token_response(
    access_token: str = "test-access-token",
) -> MagicMock:
    """
    Create a mock HTTP response that simulates a successful OAuth token exchange.
    
    Parameters:
        access_token (str): Access token value to include in the response JSON.
    
    Returns:
        MagicMock: A mock response with status_code 200 and json() returning {"access_token": access_token}.
    """
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"access_token": access_token}
    return response


def create_mock_userinfo_response(
    user_id: int = 1,
    username: str = "testuser",
    name: str = "Test User",
    email: str = "test@example.com",
    avatar_url: str = "https://gitlab.example.com/avatar.png",
) -> MagicMock:
    """Create a mock httpx response for GitLab user info.

    Args:
        user_id: GitLab user ID.
        username: GitLab username.
        name: User display name.
        email: User email.
        avatar_url: URL to user avatar.

    Returns:
        MagicMock simulating a successful user info response.
    """
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": user_id,
        "username": username,
        "name": name,
        "email": email,
        "avatar_url": avatar_url,
    }
    return response


def create_mock_httpx_client(
    token_response: MagicMock | None = None,
    userinfo_response: MagicMock | None = None,
) -> AsyncMock:
    """
    Create a configured AsyncMock that simulates an httpx.AsyncClient for OAuth token exchange and user info retrieval.
    
    Parameters:
        token_response (MagicMock | None): Mock response returned by client.post(); if None a default token response is created.
        userinfo_response (MagicMock | None): Mock response returned by client.get(); if None a default userinfo response is created.
    
    Returns:
        AsyncMock: An AsyncMock that mimics an httpx.AsyncClient where .post() returns the token response, .get() returns the userinfo response, and asynchronous context manager methods (__aenter__, __aexit__) are configured.
    """
    client = AsyncMock()
    client.post = AsyncMock(
        return_value=token_response or create_mock_token_response(),
    )
    client.get = AsyncMock(
        return_value=userinfo_response or create_mock_userinfo_response(),
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client
