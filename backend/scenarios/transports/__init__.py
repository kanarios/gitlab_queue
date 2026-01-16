"""MockTransport utilities for GitLab API testing.

This module provides httpx MockTransport-based mocking for GitLab API,
following the "don't mock what you don't own" principle.

Example:
    >>> from scenarios.transports import GitLabMockTransport
    >>> from scenarios.transports.responses import mr_response
    >>>
    >>> transport = GitLabMockTransport()
    >>> transport.register_get(
    ...     "/api/v4/projects/123/merge_requests/42",
    ...     json=mr_response(iid=42, title="Test MR")
    ... )
    >>>
    >>> client = GitLabClient(settings, transport=transport)
    >>> mr = await client.get_mr(42)
"""

from scenarios.transports.gitlab_mock_transport import GitLabMockTransport

__all__ = ["GitLabMockTransport"]
