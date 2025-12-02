"""Data models for GitLab Merge Queue Bot.

This module provides dataclass models for representing GitLab entities
and Retort configurations for serialization.
"""

from gitlab_queue.models.mr import Author, MergeRequest
from gitlab_queue.models.retorts import gitlab_retort, parse_merge_request

__all__: list[str] = [
    "Author",
    "MergeRequest",
    "gitlab_retort",
    "parse_merge_request",
]
