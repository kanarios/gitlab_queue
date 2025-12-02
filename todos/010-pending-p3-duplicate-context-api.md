---
status: completed
priority: p3
issue_id: "010"
tags: [code-review, simplicity, python]
dependencies: []
---

# Duplicate Context Management APIs

## Problem Statement

The logging module provides TWO ways to manage logging context: `LogContext` class (context manager) AND `bind_context()`/`clear_context()` functions. This violates KISS principle.

**Why it matters**: Two APIs for the same thing creates confusion about which to use. Pick one pattern.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py`
**Lines**: 251-344
**Severity**: LOW

### Evidence

```python
# Option 1: Context manager (lines 251-303)
with LogContext(request_id="abc", mr_iid=42):
    log.info("Processing")

# Option 2: Manual bind/clear (lines 305-344)
bind_context(request_id="abc", mr_iid=42)
log.info("Processing")
clear_context()
```

Both achieve the same goal. The context manager is cleaner and safer (auto-cleanup).

## Proposed Solutions

### Option A: Keep Only LogContext
**Description**: Remove `bind_context()` and `clear_context()`

**Pros**:
- Single, clear API
- Context manager ensures cleanup
- ~39 lines removed

**Cons**:
- May be awkward in some async scenarios

**Effort**: Small (30 mins)
**Risk**: Low

### Option B: Keep Both, Document When to Use Each
**Description**: Document that LogContext is preferred, bind/clear for special cases

**Pros**:
- Flexibility for edge cases

**Cons**:
- Still two APIs

**Effort**: Small (15 mins)
**Risk**: None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/utils/logging.py` (lines 305-344)

## Acceptance Criteria

- [ ] Decision made on which API to keep
- [ ] If removing bind/clear, remove from `__all__` exports
- [ ] Update docstrings to recommend preferred approach

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from simplicity review | DRY violation identified |

## Resources

- PR: Current branch `feat/config-module`
- Code Review: code-simplicity-reviewer analysis
