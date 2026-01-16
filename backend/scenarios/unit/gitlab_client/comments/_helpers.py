"""Helper functions for GitLab comment test scenarios."""

from __future__ import annotations


def create_note_response(
    note_id: int,
    body: str,
    author_id: int = 1,
    system: bool = False,
) -> dict:
    """Create a GitLab note API response for testing."""
    return {
        "id": note_id,
        "body": body,
        "system": system,
        "author": {
            "id": author_id,
            "name": "Test User",
            "username": "testuser",
        },
    }
