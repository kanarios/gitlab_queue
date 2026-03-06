"""Helper functions for auth route tests."""

from __future__ import annotations

from typing import Any

import httpx


def create_oauth_transport(
    *,
    token_response_json: dict[str, Any] | None = None,
    token_status: int = 200,
    userinfo_response_json: dict[str, Any] | None = None,
    userinfo_status: int = 200,
    project_access_status: int = 200,
    userinfo_error: Exception | None = None,
) -> httpx.MockTransport:
    """Create httpx.MockTransport that routes OAuth requests.

    Routes by request path:
    - POST */oauth/token -> token response
    - GET /api/v4/user -> userinfo response
    - GET /api/v4/projects/* -> project access response
    """
    if token_response_json is None:
        token_response_json = {"access_token": "test-access-token"}

    if userinfo_response_json is None:
        userinfo_response_json = {
            "id": 1,
            "username": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://gitlab.example.com/avatar.png",
        }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if request.method == "POST" and "/oauth/token" in path:
            return httpx.Response(
                status_code=token_status,
                json=token_response_json,
            )

        if request.method == "GET" and path == "/api/v4/user":
            if userinfo_error is not None:
                raise userinfo_error
            return httpx.Response(
                status_code=userinfo_status,
                json=userinfo_response_json if userinfo_status == 200 else {"error": "server_error"},
            )

        if request.method == "GET" and "/api/v4/projects/" in path:
            return httpx.Response(
                status_code=project_access_status,
                json={"id": 1} if project_access_status == 200 else {"message": "404 Not Found"},
            )

        return httpx.Response(status_code=404, json={"error": "not_found"})

    return httpx.MockTransport(handler)
