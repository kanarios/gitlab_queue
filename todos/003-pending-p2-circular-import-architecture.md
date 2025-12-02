---
status: completed
priority: p2
issue_id: "003"
tags: [code-review, architecture, python]
dependencies: []
---

# Circular Import Architecture Issue

## Problem Statement

`LogLevel` and `LogFormat` enums are defined in `config.py` but belong in the logging module. This creates a fragile circular dependency that's worked around with a late import inside `configure_logging()`.

**Why it matters**: This architectural issue makes the code fragile. Adding an import at module level could break the entire application with import cycles.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py`
**Lines**: 163-164
**Severity**: HIGH

### Evidence

```python
# Lines 163-164 - inside configure_logging()
# Import here to avoid circular imports
from gitlab_queue.config import LogFormat as LF
```

This comment explicitly acknowledges the circular import issue. The workaround is fragile.

### Impact
- Import cycle if anyone adds config import at module level
- Confusing module organization (logging enums in config module)
- Harder to understand module dependencies

## Proposed Solutions

### Option A: Move Enums to Logging Module
**Description**: Move `LogLevel` and `LogFormat` from `config.py` to `logging.py`

**Pros**:
- Enums are with related code
- Eliminates circular dependency
- Config imports from logging (correct direction)

**Cons**:
- Breaking change if enums are imported from config elsewhere

**Effort**: Small (1-2 hours)
**Risk**: Low

### Option B: Create Shared Types Module
**Description**: Create `gitlab_queue/types.py` with shared types

```
gitlab_queue/
├── types.py          # LogLevel, LogFormat
├── config.py         # imports from types
└── utils/
    └── logging.py    # imports from types
```

**Pros**:
- Clear separation of types
- No circular dependency possible

**Cons**:
- Additional module to maintain

**Effort**: Medium (2-3 hours)
**Risk**: Low

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/config.py` (lines 23-38)
- `backend/src/gitlab_queue/utils/logging.py` (lines 33, 163-167)

## Acceptance Criteria

- [ ] No late imports inside functions
- [ ] No circular import workarounds needed
- [ ] Enums located in appropriate module
- [ ] All existing imports updated
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from architecture review | Circular dependency is fragile |

## Resources

- PR: Current branch `feat/config-module`
- Architecture Review: architecture-strategist agent analysis
