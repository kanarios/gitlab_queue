"""Test scenarios for GitLabClient error handling.

Tests error handling including:
- 404 -> GitLabNotFoundError
- 409 -> GitLabConflictError
- 429 -> GitLabRateLimitError
- 5xx -> GitLabServerError
- Exception sanitization (no sensitive data)
"""
