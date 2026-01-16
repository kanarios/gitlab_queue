"""Queue item state constants for test scenarios."""

from enum import StrEnum


class QueueState(StrEnum):
    """Queue item processing states."""

    QUEUED = "queued"
    REBASING = "rebasing"
    TESTING = "testing"
    MERGING = "merging"
    MERGED = "merged"
    FAILED = "failed"
    CONFLICT = "conflict"
    REMOVED = "removed"
