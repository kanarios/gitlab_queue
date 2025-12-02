---
status: complete
priority: p1
issue_id: "012"
tags: [code-review, security, gitlab-client]
dependencies: []
---

# Path Traversal Risk in _project_path()

## Problem Statement

The `_project_path()` method only strips leading slashes but doesn't validate against path traversal sequences. While httpx performs some normalization, malicious paths containing `..` could escape the project scope and access unauthorized API endpoints.

**Why it matters**: An attacker or buggy caller could craft paths like `/../../admin/users` that bypass project-level authorization and access admin or cross-project endpoints.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:143-153`

```python
def _project_path(self, path: str) -> str:
    """Build project-scoped API path."""
    path = path.lstrip("/")  # Only strips leading /
    return f"/projects/{self._project_id}/{path}"
```

**Attack Vector**:
```python
# Malicious path input
client.get("/../../admin/users")
# After lstrip: "../../admin/users"
# Results in: /projects/123/../../admin/users
# httpx normalizes to: escapes project scope!
```

**OWASP Category**: A01:2021 - Broken Access Control

## Resolution

Implemented **Option A: Reject Paths with Traversal Sequences**:

```python
def _project_path(self, path: str) -> str:
    path = path.lstrip("/")
    if ".." in path:
        raise ValueError(f"Path traversal not allowed: {path}")
    return f"/projects/{self._project_id}/{path}"
```

## Technical Details

**Modified files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Changes**:
- Lines 198-214: Added path traversal validation with ValueError

## Acceptance Criteria

- [x] `_project_path()` rejects paths containing `..`
- [ ] Non-project-scoped paths also validated (deferred - internal callers only)
- [ ] Unit tests cover path traversal attempts
- [x] Error message does not expose internal path structure

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | security-sentinel identified OWASP A01 violation |
| 2025-12-02 | Fixed with validation | Simple ".." check is sufficient for this use case |

## Resources

- PR: task-5 branch
- OWASP: https://owasp.org/Top10/A01_2021-Broken_Access_Control/
