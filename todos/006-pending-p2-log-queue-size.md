---
status: completed
priority: p2
issue_id: "006"
tags: [code-review, performance, logging]
dependencies: []
---

# Log Queue Size Creates Memory/Blocking Risk

## Problem Statement

The `QueueHandler` uses a fixed queue size of 10,000 log records. During error storms, the queue can fill and block all async operations.

**Why it matters**: During incidents (API failures, database issues), logging storms can fill the queue and cause the entire application to hang.

## Findings

**File**: `/Users/artemkuznecov/repos/gitlab_queue/backend/src/gitlab_queue/utils/logging.py`
**Line**: 191
**Severity**: MEDIUM-HIGH

### Evidence

```python
log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10000)
```

### Impact Analysis
- Memory footprint: Each `LogRecord` is ~500-1000 bytes
- Queue capacity: 10,000 × 1KB = ~10MB minimum
- During error storms (1000 errors/second):
  - Queue fills in 10 seconds
  - All async event loops start blocking on logging
  - Request latency increases dramatically

## Proposed Solutions

### Option A: Increase Queue Size and Document
**Description**: Increase to 50,000 and add documentation

```python
_LOG_QUEUE_SIZE = 50000
"""Maximum number of log records to buffer.

When queue fills, logging blocks until processed.
Size chosen to handle 50 seconds of 1000 logs/sec bursts.
"""

log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=_LOG_QUEUE_SIZE)
```

**Pros**:
- Simple fix
- Handles most burst scenarios

**Cons**:
- Uses more memory (~50MB)

**Effort**: Small (15 mins)
**Risk**: Low

### Option B: Make Configurable
**Description**: Add configuration option for queue size

**Pros**:
- Tunable per deployment

**Cons**:
- More configuration complexity

**Effort**: Medium (1 hour)
**Risk**: Low

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected Files**:
- `backend/src/gitlab_queue/utils/logging.py` (line 191)

## Acceptance Criteria

- [ ] Queue size is a named constant with documentation
- [ ] Size is appropriate for expected load
- [ ] Consider making configurable if needed

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created finding from performance review | Magic number 10000 needs documentation |

## Resources

- PR: Current branch `feat/config-module`
- Performance Review: performance-oracle agent analysis
