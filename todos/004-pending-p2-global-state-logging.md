---
status: completed
priority: p2
issue_id: "004"
tags: [code-review, architecture, testing]
dependencies: []
---

# Global Mutable State in Logging Module

## Problem Statement

The logging module uses global mutable state (`_queue_listener`) without thread safety or idempotency protection. This makes testing difficult and could lead to resource leaks.

**Why it matters**: Multiple calls to `configure_logging()` leak resources (old listener not stopped). Tests can't run in parallel due to shared global state.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py`
**Lines**: 41, 161-204, 226-231
**Severity**: HIGH

### Evidence

```python
# Line 41
_queue_listener: QueueListener | None = None

# Lines 161, 199-204
def configure_logging(...):
    global _queue_listener
    ...
    _queue_listener = QueueListener(...)  # Old listener not stopped!
    _queue_listener.start()
```

### Impact
- Race conditions if called from multiple threads
- Resource leaks if called multiple times
- Tests interfere with each other
- Thread leak (QueueListener spawns background thread)

## Proposed Solutions

### Option A: Add Idempotency Guard
**Description**: Check if already configured, stop old listener before reconfiguring

```python
import threading

_queue_listener: QueueListener | None = None
_logging_lock = threading.Lock()

def configure_logging(...):
    global _queue_listener
    with _logging_lock:
        if _queue_listener is not None:
            _queue_listener.stop()  # Stop old before starting new
        # ... rest of configuration
```

**Pros**:
- Simple fix
- Prevents resource leaks
- Thread-safe

**Cons**:
- Still uses global state

**Effort**: Small (30 mins)
**Risk**: Low

### Option B: Use Singleton Class
**Description**: Encapsulate logging state in a class

```python
class LoggingManager:
    _instance: Optional['LoggingManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
```

**Pros**:
- Proper encapsulation
- Better testability

**Cons**:
- More code
- API change

**Effort**: Medium (2-3 hours)
**Risk**: Medium

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/utils/logging.py` (lines 41, 161-204, 226-231)

## Acceptance Criteria

- [ ] Multiple calls to `configure_logging()` don't leak resources
- [ ] Thread-safe access to global state
- [ ] Tests can run in parallel without interference
- [ ] `reset_logging()` function added for tests

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from architecture review | Global state causes test issues |

## Resources

- PR: Current branch `feat/config-module`
- Architecture Review: architecture-strategist, kieran-python-reviewer analysis
