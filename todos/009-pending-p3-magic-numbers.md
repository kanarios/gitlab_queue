---
status: completed
priority: p3
issue_id: "009"
tags: [code-review, quality, python]
dependencies: []
---

# Magic Numbers Should Be Named Constants

## Problem Statement

Several magic numbers are used inline without named constants or documentation explaining their significance.

**Why it matters**: Named constants make code self-documenting and easier to maintain. When you need to change a value, you change it in one place.

## Findings

**Files**:
- `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/config.py` (line 347)
- `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py` (line 191)

**Severity**: LOW

### Evidence

```python
# config.py line 347
if jwt_secret_len < 64:  # Why 64? Document this!

# logging.py line 191
queue.Queue(maxsize=10000)  # Why 10000?
```

## Proposed Solutions

### Option A: Extract Named Constants
**Description**: Create named constants with documentation

```python
# config.py
JWT_SECRET_MIN_LENGTH = 64  # 256 bits for HMAC-SHA256 security

# logging.py
LOG_QUEUE_MAX_SIZE = 10000  # Maximum queued log records before blocking
```

**Pros**:
- Self-documenting code
- Single source of truth
- Easy to find and modify

**Cons**:
- Slightly more code

**Effort**: Small (15 mins)
**Risk**: None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/config.py` (line 347)
- `backend/src/gitlab_queue/utils/logging.py` (line 191)

## Acceptance Criteria

- [ ] Magic numbers replaced with named constants
- [ ] Constants have docstrings explaining significance
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from code review | Document magic numbers |

## Resources

- PR: Current branch `feat/config-module`
- Code Review: pattern-recognition-specialist analysis
