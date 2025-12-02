---
status: pending
priority: p3
issue_id: "017"
tags: [code-review, simplification, gitlab-client]
dependencies: ["011"]
---

# Simplify Exception Hierarchy (YAGNI)

## Problem Statement

The GitLab client defines 5 custom exception classes, but none are caught or handled differently anywhere in the codebase. This is premature abstraction - the complex hierarchy adds code without current value.

**Why it matters**: Unused code is maintenance burden. Simpler code is easier to understand and modify.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:41-78`

**Current Hierarchy (5 classes, ~37 lines)**:
```python
GitLabAPIError (base)
├── GitLabNotFoundError (404)
├── GitLabConflictError (409)
├── GitLabRateLimitError (429 with retry_after)
└── GitLabServerError (5xx)
```

**Usage Analysis**: No caller handles these differently - they all bubble up as errors.

**Note**: After fixing P1 issue #011 (data exposure), reconsider this simplification as it may now be needed for error handling logic.

## Proposed Solutions

### Option A: Keep Only Base with Status Code (Aggressive Simplification)
```python
class GitLabAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
```

**Pros**: Maximum simplification, 30+ lines saved
**Cons**: Loses semantic meaning, harder to catch specific errors later
**Effort**: Small (30 minutes)
**Risk**: Medium (may need to re-add later)

### Option B: Keep for Future Use (Do Nothing)
Wait until Tasks 6-8 when error handling becomes important.

**Pros**: No work now
**Cons**: Unused code in meantime
**Effort**: None
**Risk**: None

### Option C: Add Usage Before Keeping (Recommended)
Document when each exception type should be caught differently.

**Pros**: Justifies keeping hierarchy
**Cons**: May reveal they're not needed
**Effort**: Small (1 hour)
**Risk**: Low

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Lines to potentially remove**: 55-78 (if simplifying)

## Acceptance Criteria

- [ ] Decision made on exception hierarchy
- [ ] If keeping: document usage cases
- [ ] If simplifying: update all raise statements

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | code-simplicity-reviewer flagged YAGNI |

## Resources

- PR: task-5 branch
- Depends on P1 fix #011
