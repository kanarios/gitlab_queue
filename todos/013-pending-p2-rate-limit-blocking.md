---
status: pending
priority: p2
issue_id: "013"
tags: [code-review, performance, security, gitlab-client]
dependencies: []
---

# Rate Limit Handling Blocks All Requests

## Problem Statement

The current rate limit handling implementation blocks ALL requests during the wait period, not just the failing request. This creates a potential DoS condition where a single rate-limited request can block the entire client for up to 25 minutes (5 retries x 300 seconds max).

**Why it matters**: In a production scenario with multiple concurrent requests, hitting a rate limit on one endpoint blocks all other API calls, causing cascading failures and poor user experience.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:276-286, 318-332`

```python
async def _handle_rate_limit(self, error: GitLabRateLimitError) -> None:
    wait_seconds = error.retry_after or 60  # Default 60s
    wait_seconds = min(wait_seconds, 300)   # Cap at 5 minutes
    await asyncio.sleep(wait_seconds)        # BLOCKS entire coroutine
```

**Worst Case Calculation**:
- 5 retries (default `api_max_retries`)
- x 300 seconds max wait
- = **25 minutes total blocking**

**Impact**:
- Memory buildup from queued requests
- Application hangs during rate limit
- No way to cancel or timeout stuck requests

## Proposed Solutions

### Option A: Client-Level Rate Limit Semaphore (Recommended)
Implement a shared rate limit state that all requests check before executing.

```python
class GitLabClient:
    def __init__(self, settings: Settings) -> None:
        self._rate_limit_lock = asyncio.Lock()
        self._rate_limit_until: float | None = None

    async def _check_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            if self._rate_limit_until and time.time() < self._rate_limit_until:
                wait_time = self._rate_limit_until - time.time()
                await asyncio.sleep(wait_time)
                self._rate_limit_until = None
```

**Pros**: Efficient, allows requests to proceed after rate limit expires
**Cons**: Adds complexity
**Effort**: Medium (2-3 hours)
**Risk**: Low

### Option B: Reduce Max Retries for Rate Limits
Separate rate limit retry count from other retries, limit to 2-3 attempts.

**Pros**: Simple change
**Cons**: Doesn't fix fundamental blocking issue
**Effort**: Small (30 minutes)
**Risk**: Low

### Option C: Add Global Request Timeout
Add a maximum timeout per request that overrides rate limit waits.

**Pros**: Prevents indefinite blocking
**Cons**: May fail requests that could succeed
**Effort**: Small (1 hour)
**Risk**: Medium

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Lines to modify**: 276-286 (rate limit handler), 318-332 (retry logic)

**Configuration change**: Consider adding `rate_limit_max_wait_seconds` to Settings

## Acceptance Criteria

- [ ] Rate limit on one request doesn't block other requests
- [ ] Total wait time is bounded (configurable max)
- [ ] Rate limit state is tracked at client level
- [ ] Unit tests verify rate limit handling doesn't cascade

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | performance-oracle and security-sentinel both flagged |

## Resources

- PR: task-5 branch
