"""GitLab Mock Transport for httpx-based testing.

This module provides a MockTransport implementation specifically designed
for testing GitLab API interactions without external dependencies.

Based on James Bennett's article "Don't mock Python's HTTPX":
https://www.b-list.org/weblog/2023/dec/08/mock-python-httpx/
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class RegisteredHandler:
    """A registered response handler with its matching criteria."""

    method: str
    path_pattern: str | re.Pattern[str]
    handler: Callable[[httpx.Request], httpx.Response]


class GitLabMockTransport(httpx.AsyncBaseTransport):
    """Async mock transport for GitLab API testing.

    Provides fluent API for registering responses and supports:
    - Exact path matching
    - Regex path patterns
    - Response sequences (for retry testing)
    - Request history tracking

    Example:
        >>> transport = GitLabMockTransport()
        >>> transport.register_get(
        ...     "/api/v4/projects/123/merge_requests/42",
        ...     json={"iid": 42, "title": "Test MR"}
        ... )
        >>>
        >>> client = GitLabClient(settings, transport=transport)
        >>> mr = await client.get_mr(42)  # Returns mocked response
    """

    def __init__(self) -> None:
        """Initialize empty mock transport."""
        self._handlers: list[RegisteredHandler] = []
        self._history: list[httpx.Request] = []

    def register(
        self,
        method: str,
        path: str | re.Pattern[str],
        *,
        status: int = 200,
        json_data: dict[str, Any] | list[Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> GitLabMockTransport:
        """Register a response for method + path combination.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: URL path or regex pattern to match.
            status: HTTP status code (default: 200).
            json_data: JSON response body (will be serialized).
            content: Raw bytes response body.
            headers: Response headers.

        Returns:
            Self for fluent API chaining.
        """
        response_headers = {"content-type": "application/json", **(headers or {})}

        if json_data is not None:
            response_content = json.dumps(json_data).encode()
        elif content is not None:
            response_content = content
        else:
            response_content = b""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=status,
                content=response_content,
                headers=response_headers,
            )

        self._handlers.append(RegisteredHandler(method, path, handler))
        return self

    def register_get(
        self,
        path: str | re.Pattern[str],
        **kwargs: Any,
    ) -> GitLabMockTransport:
        """Register a GET response."""
        return self.register("GET", path, **kwargs)

    def register_post(
        self,
        path: str | re.Pattern[str],
        **kwargs: Any,
    ) -> GitLabMockTransport:
        """Register a POST response."""
        return self.register("POST", path, **kwargs)

    def register_put(
        self,
        path: str | re.Pattern[str],
        **kwargs: Any,
    ) -> GitLabMockTransport:
        """Register a PUT response."""
        return self.register("PUT", path, **kwargs)

    def register_delete(
        self,
        path: str | re.Pattern[str],
        **kwargs: Any,
    ) -> GitLabMockTransport:
        """Register a DELETE response."""
        return self.register("DELETE", path, **kwargs)

    def register_handler(
        self,
        method: str,
        path: str | re.Pattern[str],
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> GitLabMockTransport:
        """Register a custom handler function.

        Use this for complex response logic (e.g., based on request body).

        Args:
            method: HTTP method.
            path: URL path or regex pattern.
            handler: Function that takes Request and returns Response.

        Returns:
            Self for fluent API chaining.
        """
        self._handlers.append(RegisteredHandler(method, path, handler))
        return self

    def register_sequence(
        self,
        method: str,
        path: str | re.Pattern[str],
        responses: list[httpx.Response],
    ) -> GitLabMockTransport:
        """Register a sequence of responses (for retry/polling tests).

        Each call returns the next response in sequence. After exhaustion,
        returns 404.

        Args:
            method: HTTP method.
            path: URL path or regex pattern.
            responses: List of responses to return in order.

        Returns:
            Self for fluent API chaining.
        """
        iterator = iter(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            try:
                return next(iterator)
            except StopIteration:
                return self._not_found_response(request)

        self._handlers.append(RegisteredHandler(method, path, handler))
        return self

    @property
    def history(self) -> list[httpx.Request]:
        """Return list of all requests made through this transport.

        Returns a copy to prevent external modification.
        """
        return self._history.copy()

    @property
    def call_count(self) -> int:
        """Return total number of requests made."""
        return len(self._history)

    def get_request(self, index: int = -1) -> httpx.Request:
        """Get a specific request from history.

        Args:
            index: Request index (default: -1 for last request).

        Returns:
            The request at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        return self._history[index]

    def get_request_json(self, index: int = -1) -> dict[str, Any]:
        """Get JSON body from a specific request.

        Args:
            index: Request index (default: -1 for last request).

        Returns:
            Parsed JSON body.

        Raises:
            IndexError: If index is out of range.
            json.JSONDecodeError: If body is not valid JSON.
        """
        request = self._history[index]
        result: dict[str, Any] = json.loads(request.content.decode())
        return result

    def assert_called(self) -> None:
        """Assert that at least one request was made.

        Raises:
            AssertionError: If no requests were made.
        """
        assert len(self._history) > 0, "Expected at least one request, but none were made"

    def assert_called_once(self) -> None:
        """Assert that exactly one request was made.

        Raises:
            AssertionError: If request count is not exactly 1.
        """
        assert len(self._history) == 1, f"Expected exactly 1 request, but {len(self._history)} were made"

    def assert_called_with_path(self, path: str) -> None:
        """Assert that a request was made to the specified path.

        Args:
            path: Expected URL path.

        Raises:
            AssertionError: If no request to the path was found.
        """
        paths = [str(r.url.path) for r in self._history]
        assert path in paths, f"Expected request to {path}, but got requests to: {paths}"

    def clear_history(self) -> None:
        """Clear the request history."""
        self._history.clear()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request.

        This is the main entry point called by httpx.AsyncClient.

        Args:
            request: The HTTP request to handle.

        Returns:
            Mocked HTTP response.
        """
        self._history.append(request)

        for registered in self._handlers:
            if request.method != registered.method:
                continue

            path = request.url.path
            pattern = registered.path_pattern

            if isinstance(pattern, re.Pattern):
                if pattern.search(path):
                    return registered.handler(request)
            elif path == pattern:
                return registered.handler(request)

        return self._not_found_response(request)

    def _not_found_response(self, request: httpx.Request) -> httpx.Response:
        """Generate a 404 response for unregistered paths."""
        error_body = {
            "message": f"No mock registered for {request.method} {request.url.path}",
            "registered_handlers": [f"{h.method} {h.path_pattern}" for h in self._handlers],
        }
        return httpx.Response(
            status_code=404,
            content=json.dumps(error_body).encode(),
            headers={"content-type": "application/json"},
        )


def create_json_response(
    status: int = 200,
    json_data: dict[str, Any] | list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Create an httpx.Response with JSON content.

    Helper function for building responses for register_sequence.

    Args:
        status: HTTP status code.
        json_data: JSON-serializable data.
        headers: Additional headers.

    Returns:
        httpx.Response instance.
    """
    response_headers = {"content-type": "application/json", **(headers or {})}
    content = json.dumps(json_data).encode() if json_data is not None else b""

    return httpx.Response(
        status_code=status,
        content=content,
        headers=response_headers,
    )


__all__ = ["GitLabMockTransport", "create_json_response"]
