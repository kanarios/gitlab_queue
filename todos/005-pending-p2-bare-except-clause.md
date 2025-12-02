---
status: completed
priority: p2
issue_id: "005"
tags: [code-review, quality, python]
dependencies: []
---

# Bare Exception Clause in Database URL Masking

## Problem Statement

The `_mask_database_url` function catches generic `Exception` and silently suppresses it. This could hide unexpected errors and make debugging difficult.

**Why it matters**: Silent error handling masks bugs. If the URL parsing logic has a bug, you'll never know.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/config.py`
**Lines**: 215-216
**Severity**: MEDIUM

### Evidence

```python
# Lines 215-216
except Exception:
    pass
```

This swallows ALL exceptions silently, including:
- TypeError (wrong types)
- AttributeError (missing attributes)
- Any unexpected error from urlparse

## Proposed Solutions

### Option A: Narrow Exception Types
**Description**: Catch only expected exceptions

```python
except (ValueError, AttributeError):
    # URL parsing failed, return unmasked (safe for logging context)
    pass
```

**Pros**:
- Explicit about expected failures
- Unexpected errors propagate

**Cons**:
- May need to update if new exceptions found

**Effort**: Small (10 mins)
**Risk**: Low

### Option B: Log and Continue
**Description**: Log the error for debugging but continue

```python
except Exception as e:
    # Can't log yet (circular dependency), but at least document
    # In production, consider a debug flag to print to stderr
    pass  # URL masking failed, return unmasked
```

**Pros**:
- Visibility into failures

**Cons**:
- Logging module not available here (circular dependency)

**Effort**: Small (10 mins)
**Risk**: Low

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/config.py` (lines 215-216)

## Acceptance Criteria

- [ ] Bare `except Exception` replaced with specific exception types
- [ ] Unexpected exceptions propagate

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from code review | Silent exception handling is problematic |

## Resources

- PR: Current branch `feat/config-module`
- Code Review: kieran-python-reviewer analysis
