"""Response factories for GitLab API mocking.

These factories create valid GitLab API response dictionaries
that match the expected schema from GitLab's API.

Example:
    >>> from scenarios.transports.responses import mr_response, pipeline_response
    >>>
    >>> transport.register_get(
    ...     "/api/v4/projects/123/merge_requests/42",
    ...     json=mr_response(iid=42, title="My MR")
    ... )
"""

from scenarios.transports.responses.error_responses import (
    conflict_response,
    not_found_response,
    rate_limit_response,
    server_error_response,
)
from scenarios.transports.responses.mr_responses import mr_response, note_response
from scenarios.transports.responses.pipeline_responses import job_response, pipeline_response

__all__ = [
    "conflict_response",
    "job_response",
    "mr_response",
    "not_found_response",
    "note_response",
    "pipeline_response",
    "rate_limit_response",
    "server_error_response",
]
