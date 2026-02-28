"""Mock for GitLab GET /projects/:id endpoint.

Provides a helper to create matcher/response pair for the project endpoint.
"""

from __future__ import annotations

import jj


def make_project_mock(
    mock_url: str,
    project_id: int = 123,
) -> tuple[jj.Matcher, jj.Response]:
    """Create matcher/response pair for GitLab GET /projects/:id.

    Args:
        mock_url: Base URL of the mock server.
        project_id: GitLab project ID.

    Returns:
        Tuple of (matcher, response) for use with jj.mock.mocked().
    """
    matcher = jj.match("GET", f"/api/v4/projects/{project_id}")
    response = jj.Response(
        status=200,
        json={"id": project_id, "web_url": f"{mock_url}/test/project"},
    )
    return matcher, response


__all__ = ["make_project_mock"]
