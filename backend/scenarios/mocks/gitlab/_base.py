"""Base configuration for GitLab API mocks.

Provides common settings and utilities used by all GitLab mock modules.
"""

from __future__ import annotations

import os

# Default JJ mock server URL - can be overridden via environment variable
JJ_MOCK_URL = os.environ.get("JJ_MOCK_URL", "http://localhost:8080")


def get_mock_url() -> str:
    """Get the JJ mock server URL.

    Returns:
        str: The mock server URL from environment or default.
    """
    return JJ_MOCK_URL
