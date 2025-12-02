---
status: pending
priority: p2
issue_id: "015"
tags: [code-review, performance, gitlab-client]
dependencies: []
---

# Retry Strategy Improvements

## Problem Statement

The current retry strategy has several issues:
1. Rate limit errors consume the retry budget (should be separate)
2. Network errors (timeouts, connection failures) are NOT retried
3. All operations use same retry config (can't differentiate GET from POST)

**Why it matters**: Network hiccups cause permanent failures, and hitting rate limits during high load wastes retry budget unnecessarily.

## Findings

**Location**: `backend/src/gitlab_queue/clients/gitlab.py:318-332`

```python
async for attempt in AsyncRetrying(
    retry=retry_if_exception_type((GitLabServerError, GitLabRateLimitError)),  # Missing: network errors
    stop=stop_after_attempt(self._max_retries),  # Rate limits count against this!
    wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
    reraise=True,
):
```

**Missing from retry list**:
- `httpx.ConnectError`
- `httpx.NetworkError`
- `httpx.ReadTimeout`
- `httpx.TimeoutException`

**Problem with rate limits**:
- Rate limits are flow control, not errors
- They shouldn't consume retry budget

## Proposed Solutions

### Option A: Add Network Errors to Retry List (Quick Fix)
Add httpx network exceptions to the retryable list.

```python
from httpx import ConnectError, NetworkError, ReadTimeout, TimeoutException

retry=retry_if_exception_type((
    GitLabServerError,
    ConnectError,
    NetworkError,
    ReadTimeout,
    TimeoutException,
))
```

**Pros**: Simple fix, immediate improvement
**Cons**: Doesn't fix rate limit budget issue
**Effort**: Small (15 minutes)
**Risk**: Low

### Option B: Separate Rate Limit Handling from Retry Loop (Recommended)
Handle rate limits outside the retry counter.

```python
async for attempt in AsyncRetrying(
    retry=retry_if_exception_type((GitLabServerError, ConnectError, ...)),
    # Rate limits handled separately, don't consume retries
):
    with attempt:
        try:
            response = await self._client.request(...)
            self._handle_error_response(response)
            return response
        except GitLabRateLimitError as e:
            await self._handle_rate_limit(e)
            continue  # Don't count as retry
```

**Pros**: Proper handling of rate limits
**Cons**: More complex change
**Effort**: Medium (1-2 hours)
**Risk**: Low

### Option C: Injectable Retry Policy per Operation
Make retry strategy injectable for different operation types.

**Pros**: Maximum flexibility for Tasks 6-8
**Cons**: Over-engineering for now
**Effort**: Large (4+ hours)
**Risk**: Medium

## Recommended Action

<!-- Fill in after triage -->

## Technical Details

**Affected files**:
- `backend/src/gitlab_queue/clients/gitlab.py`

**Lines to modify**: 318-332

## Acceptance Criteria

- [ ] Network errors (timeouts, connection) are retried
- [ ] Rate limits don't consume retry budget
- [ ] Retry behavior is configurable
- [ ] Unit tests cover retry scenarios

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-02 | Created from code review | performance-oracle flagged retry issues |

## Resources

- PR: task-5 branch
