---
status: completed
priority: p2
issue_id: "007"
tags: [code-review, quality, python]
dependencies: []
---

# Import Inside Method (hmac)

## Problem Statement

The `Secret.__eq__` method imports `hmac` inside the method body instead of at module level. This is inconsistent with Python conventions.

**Why it matters**: Late imports are only acceptable for circular dependency resolution, not for standard library modules. This inconsistency makes the code harder to maintain.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/config.py`
**Line**: 80
**Severity**: MEDIUM

### Evidence

```python
def __eq__(self, other: object) -> bool:
    if not isinstance(other, Secret):
        return NotImplemented
    import hmac  # Import inside method - should be at module level

    self_value: str = object.__getattribute__(self, "_secret_value")
    other_value: str = object.__getattribute__(other, "_secret_value")
    return hmac.compare_digest(self_value, other_value)
```

## Proposed Solutions

### Option A: Move Import to Module Level
**Description**: Move `import hmac` to top of file

```python
# At top of file with other imports
import hmac
from enum import Enum
```

**Pros**:
- Standard Python convention
- Clear dependencies at top of file
- Slightly faster on first call

**Cons**:
- None

**Effort**: Small (5 mins)
**Risk**: None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/config.py` (line 80)

## Acceptance Criteria

- [ ] `import hmac` moved to module level
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from code review | Follow Python conventions for imports |

## Resources

- PR: Current branch `feat/config-module`
- Code Review: kieran-python-reviewer analysis
