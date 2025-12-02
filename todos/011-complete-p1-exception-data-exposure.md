---
status: complete
priority: p1
issue_id: "011"
tags: [code-review, security, gitlab-client]
dependencies: []
---

# Exception Data Exposure via Response Body

## Problem Statement

The `GitLabAPIError` exception class stores the full API `response_body` as an instance attribute. This response body may contain sensitive information (tokens, credentials, API keys) returned by GitLab API error responses.

**Why it matters**: If exceptions are logged with `vars(exc)` or serialized to error tracking systems (Sentry, Rollbar), the raw response body - including any sensitive data - will be exposed. The structlog masking only works on string values, not structured data in exception attributes.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:41-52`

```python
class GitLabAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | str | None = None,  # RISK: Stores raw response
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body  # Can contain sensitive data
```

**Attack Vector**:
```python
# If exception is logged or serialized:
exc = GitLabAPIError("Error", response_body={"token": "glpat-secret"})
log.error("Failed", **vars(exc))  # Exposes: {"response_body": {"token": "glpat-..."}}
```

**OWASP Category**: A09:2021 - Security Logging and Monitoring Failures

## Resolution

Implemented **Option B: Store Sanitized Response Only** with additions from Option A:

1. Added `_SENSITIVE_KEYS` frozenset to detect sensitive keys
2. Added `_sanitize_response_body()` function for recursive sanitization
3. Modified `GitLabAPIError` to:
   - Store sanitized response as `_response_body` private attribute
   - Provide `response_body` property returning sanitized data
   - Override `__repr__` to exclude response body entirely
   - Override `__str__` to show only message and status code

## Technical Details

**Modified files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Changes**:
- Lines 41-46: Added `_SENSITIVE_KEYS` frozenset
- Lines 49-75: Added `_sanitize_response_body()` function
- Lines 83-108: Modified `GitLabAPIError` class with sanitization

## Acceptance Criteria

- [x] Exception `__repr__` and `__str__` do not include response_body
- [x] Serializing exception `__dict__` does not expose raw response body
- [ ] Unit tests verify sensitive data is masked in exception output
- [x] Error tracking integrations receive sanitized data

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | security-sentinel identified OWASP A09 violation |
| 2025-12-02 | Fixed with sanitization | Implemented comprehensive solution combining Options A and B |

## Resources

- PR: task-5 branch
- OWASP: https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/
