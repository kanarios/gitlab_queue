"""Label constants for test scenarios."""

from enum import StrEnum


class Labels(StrEnum):
    """GitLab labels used in merge queue."""

    MERGE_QUEUE = "merge_queue"
    HOTFIX = "hotfix"
    FEATURE = "feature"
    BUG = "bug"
    URGENT = "urgent"
