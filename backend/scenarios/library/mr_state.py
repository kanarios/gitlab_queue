"""MR state constants for test scenarios."""

from enum import StrEnum


class MRState(StrEnum):
    """GitLab MR states."""

    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"
