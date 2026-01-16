"""Common constants for d42 schemas."""

# GitLab limits
MAX_LABELS = 50  # GitLab label limit

# Git SHA-1 hex length
SHA_LENGTH = 40

# ISO 8601 datetime string pattern
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"

__all__ = [
    "DATETIME_PATTERN",
    "MAX_LABELS",
    "SHA_LENGTH",
]
