"""Helper functions for auth route tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def create_mock_token_response(
    access_token: str = "test-access-token",
) -> MagicMock:
    """Create a mock httpx response for OAuth token exchange.

    Args:
        access_token: The access token to return.

    Returns:
        MagicMock simulating a successful token exchange response.
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
    """Create a mock httpx.AsyncClient for auth route testing.

    Configures .post() for token exchange and .get() for user info fetch.

    Args:
        token_response: Mock response for token exchange POST.
        userinfo_response: Mock response for user info GET.

    Returns:
        AsyncMock configured as an httpx.AsyncClient.
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
