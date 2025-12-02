---
status: pending
priority: p2
issue_id: "014"
tags: [code-review, performance, gitlab-client]
dependencies: []
---

# Missing Response Body Size Limits

## Problem Statement

The client has no limits on response body size. `response.json()` and `response.text` load entire responses into memory, which could lead to OOM crashes when receiving large responses (e.g., large MR diffs).

**Why it matters**: GitLab API can return very large responses (100MB+ for MR diffs). Multiple concurrent large responses could crash the application.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:183-192, 364, 387, 412, 437`

```python
def _parse_response_body(self, response: httpx.Response) -> dict[str, Any] | str | None:
    try:
        body: dict[str, Any] = response.json()  # No size check!
        return body
    except Exception:
        text = response.text  # No size check!
        return text if text else None
```

**Vulnerable Endpoints**:
- `/projects/{id}/merge_requests/{iid}/changes` - Full MR diff
- `/projects/{id}/repository/commits` - Large commit history
- `/projects/{id}/repository/files/{path}/raw` - Large files

## Proposed Solutions

### Option A: Check Content-Length Before Parsing (Recommended)
Add content-length check before parsing response body.

```python
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB

def _parse_response_body(self, response: httpx.Response) -> dict[str, Any] | str | None:
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_RESPONSE_SIZE:
        log.warning("Response too large", content_length=content_length)
        return {"error": "Response body too large", "truncated": True}
    # ... existing code
```

**Pros**: Simple, catches most cases
**Cons**: Not all responses have Content-Length header
**Effort**: Small (30 minutes)
**Risk**: Low

### Option B: Configure httpx with max_response_size
Not directly supported by httpx, but can use stream-based reading with limit.

**Pros**: More robust
**Cons**: More complex implementation
**Effort**: Medium (2 hours)
**Risk**: Medium

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Lines to modify**: 183-192, potentially add to `__init__` as configuration

## Acceptance Criteria

- [ ] Large responses (>10MB) are detected before loading
- [ ] Application doesn't crash on large responses
- [ ] Warning logged for truncated responses
- [ ] Unit tests verify size limit behavior

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | performance-oracle flagged OOM risk |

## Resources

- PR: task-5 branch
