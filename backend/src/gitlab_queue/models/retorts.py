"""Adaptix Retort configurations for data serialization.

Provides Retort instances for converting between:
- GitLab API JSON responses → dataclass models
- Dataclass models → SQLite storage format
"""

from __future__ import annotations

from typing import Any

from adaptix import P, Retort, name_mapping

from gitlab_queue.models.mr import Author, MergeRequest


def _extract_labels(labels: list[Any]) -> list[str]:
    """Extract label names from GitLab API response.

    GitLab API can return labels as either:
    - List of strings: ["label1", "label2"]
    - List of objects: [{"name": "label1"}, {"name": "label2"}]

    Args:
        labels: Labels from API response

    Returns:
        List of label name strings
    """
    if not labels:
        return []
    first = labels[0]
    if isinstance(first, dict):
        return [str(label["name"]) for label in labels]
    return [str(label) for label in labels]


# Retort for parsing GitLab API responses into dataclass models
gitlab_retort = Retort(
    recipe=[
        # Map GitLab API field names to our dataclass field names
        name_mapping(
            P[MergeRequest],
            map={
                "has_conflicts": ("has_conflicts", "detailed_merge_status"),
            },
            extra_in="skip",  # Skip unknown fields from API
        ),
        name_mapping(
            P[Author],
            extra_in="skip",  # Skip unknown fields from API
        ),
    ]
)


def parse_merge_request(data: dict[str, Any]) -> MergeRequest:
    """Parse GitLab API response into MergeRequest model.

    Handles the complexity of GitLab API response format including
    nested author object and label extraction.

    Args:
        data: Raw JSON response from GitLab API

    Returns:
        MergeRequest instance
    """
    # Extract and normalize data for our model
    author_data = data.get("author", {})
    author = Author(
        id=author_data.get("id", 0),
        name=author_data.get("name", ""),
        username=author_data.get("username", ""),
        avatar_url=author_data.get("avatar_url"),
    )

    # Determine has_conflicts from multiple possible fields
    has_conflicts = data.get("has_conflicts", False)
    if not has_conflicts:
        # Check detailed_merge_status for conflict indicators
        detailed_status = data.get("detailed_merge_status", "")
        has_conflicts = detailed_status in ("conflict", "has_conflicts")

    return MergeRequest(
        iid=data["iid"],
        title=data["title"],
        state=data["state"],
        labels=_extract_labels(data.get("labels", [])),
        sha=data.get("sha", ""),
        source_branch=data["source_branch"],
        target_branch=data["target_branch"],
        merge_status=data.get("merge_status", ""),
        author=author,
        has_conflicts=has_conflicts,
        rebase_in_progress=data.get("rebase_in_progress", False),
        web_url=data.get("web_url"),
    )


__all__: list[str] = ["gitlab_retort", "parse_merge_request"]
